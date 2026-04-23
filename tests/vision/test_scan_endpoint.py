"""Integration tests for POST /scan with a mocked Opus Vision call.

Zero API cost: `api.scan._call_opus_vision` is patched to return a canned
JSON string. This covers the wiring the unit tests can't — data-URL decode,
prompt loading, normalizer integration, run-log writing, PHI stripping,
and the retry path.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import patch

# See conftest.py — the macOS Anaconda TF-mutex deadlock fires if transformers
# gets pulled with its TF backend enabled. Force USE_TF=0 at import time.
os.environ.setdefault("USE_TF", "0")

import pytest
from fastapi.testclient import TestClient

from api import scan as scan_mod
from api.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tiny_png_data_url() -> str:
    """A 1×1 PNG encoded as a data URL. Enough to satisfy the endpoint's
    decode step; Opus is mocked so it never actually processes the bytes.
    """
    # Canonical 1x1 transparent PNG.
    png = bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


_FAKE_OPUS_JSON = json.dumps({
    "patient": {"age": 42, "sex": "f", "name": "Jan Kowalski", "pesel": "92010112345"},
    "lab_name": "DIAGNOSTYKA",
    "collected_at": "2026-03-11",
    "parameters": [
        {"name": "Hemoglobina", "value": 14.2, "unit": "g/dL", "confidence": "high"},
        {"name": "Leukocyty",   "value": 6.8,  "unit": "10^9/L"},
        {"name": "Kreatynina",  "value": 0.9,  "unit": "mg/dL"},
    ],
    "confidence": "high",
    "notes": "clean scan, PESEL 92010112345 visible on the sheet",
})

_FAKE_NON_JSON = "I cannot read this image, sorry."

_FAKE_JSON_AFTER_RETRY = json.dumps({
    "parameters": [
        {"name": "HGB", "value": 14.0, "unit": "g/dL"},
    ],
    "confidence": "medium",
})


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    """Give each test its own runs/ dir so log assertions don't collide."""
    monkeypatch.setattr(scan_mod, "RUNS_DIR", tmp_path / "runs")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_scan_endpoint_returns_normalized_values(client: TestClient):
    with patch.object(
        scan_mod, "_call_opus_vision",
        return_value=(_FAKE_OPUS_JSON, 2500, 0.03),
    ) as mock_call:
        resp = client.post("/scan", json={
            "imageDataUrl": _tiny_png_data_url(),
            "age": 42,
            "sex": "f",
        })

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Polish synonyms + Polish unit must be normalized.
    assert body["values"]["HGB"] == pytest.approx(14.2)
    assert body["values"]["WBC"] == pytest.approx(6.8)         # 10^9/L → K/uL identity
    assert body["values"]["CREATININE"] == pytest.approx(0.9)
    # "high" overall confidence spreads to all params.
    for p in ("HGB", "WBC", "CREATININE"):
        assert body["confidence"][p] == pytest.approx(0.9)
    assert body["collectedAt"] == "2026-03-11"

    # Exactly one Opus call (no retry for valid JSON).
    assert mock_call.call_count == 1


def test_scan_endpoint_strips_phi_before_logging(client: TestClient):
    with patch.object(
        scan_mod, "_call_opus_vision",
        return_value=(_FAKE_OPUS_JSON, 2500, 0.03),
    ):
        resp = client.post("/scan", json={
            "imageDataUrl": _tiny_png_data_url(),
            "age": 42, "sex": "f",
        })
    assert resp.status_code == 200

    # Log file was written — and must NOT contain name or PESEL.
    log_files = list(scan_mod.RUNS_DIR.glob("*.jsonl"))
    assert len(log_files) == 1
    content = log_files[0].read_text()
    assert "Jan Kowalski" not in content
    assert "92010112345" not in content
    # But the image hash is present.
    assert '"image_sha":' in content
    # And the numeric values survive.
    record = json.loads(content.splitlines()[-1])
    assert record["values"]["HGB"] == pytest.approx(14.2)
    assert record["prompt_version"] == "v1"
    assert record["latency_ms"] == 2500


# ---------------------------------------------------------------------------
# Retry path
# ---------------------------------------------------------------------------

def test_scan_endpoint_retries_on_non_json_output(client: TestClient):
    with patch.object(scan_mod, "_call_opus_vision") as mock_call:
        mock_call.side_effect = [
            (_FAKE_NON_JSON,        1500, 0.015),
            (_FAKE_JSON_AFTER_RETRY, 1800, 0.018),
        ]
        resp = client.post("/scan", json={
            "imageDataUrl": _tiny_png_data_url(),
            "age": 42, "sex": "m",
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["values"]["HGB"] == pytest.approx(14.0)
    assert body["confidence"]["HGB"] == pytest.approx(0.6)    # "medium" → 0.6
    assert mock_call.call_count == 2

    # Retry latency + cost are summed into the log.
    log = list(scan_mod.RUNS_DIR.glob("*.jsonl"))[0]
    rec = json.loads(log.read_text().splitlines()[-1])
    assert rec["latency_ms"] == 3300
    assert rec["cost_estimate_usd"] == pytest.approx(0.033)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_scan_endpoint_rejects_bad_data_url(client: TestClient):
    resp = client.post("/scan", json={"imageDataUrl": "not-a-data-url"})
    assert resp.status_code == 400
    assert "data url" in resp.json()["detail"].lower()


def test_scan_endpoint_returns_503_when_sdk_missing(client: TestClient):
    with patch.object(
        scan_mod, "_call_opus_vision",
        side_effect=RuntimeError("anthropic SDK not installed"),
    ):
        resp = client.post("/scan", json={"imageDataUrl": _tiny_png_data_url()})
    assert resp.status_code == 503
    assert "anthropic" in resp.json()["detail"].lower()


def test_scan_endpoint_returns_502_on_parse_failure_even_after_retry(client: TestClient):
    with patch.object(scan_mod, "_call_opus_vision") as mock_call:
        mock_call.side_effect = [
            (_FAKE_NON_JSON, 1500, 0.015),
            (_FAKE_NON_JSON, 1500, 0.015),
        ]
        resp = client.post("/scan", json={"imageDataUrl": _tiny_png_data_url()})
    assert resp.status_code == 502
    assert mock_call.call_count == 2


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def test_load_prompt_strips_header_matter():
    prompt = scan_mod._load_prompt("v1")
    # The prompt MUST NOT leak the markdown heading section.
    assert "Scan OCR prompt — v1" not in prompt
    # And it must include the key instructions.
    assert "lab result sheet" in prompt
    assert "JSON" in prompt


def test_load_prompt_missing_version_raises():
    with pytest.raises(FileNotFoundError):
        scan_mod._load_prompt("v_does_not_exist_99")
