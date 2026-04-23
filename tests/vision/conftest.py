"""Pytest fixtures for the Vision validation harness.

Cache-first design: by default every test uses a committed `.cache.json`
sibling next to the image (zero API calls). The `--live` flag makes the
opus_client hit the real Anthropic API and refresh the cache. The
`--prompt=vN` flag swaps the prompt version and isolates the cache under
`<stem>.cache.<vN>.json` so champion/challenger comparisons don't stomp
each other.
"""
from __future__ import annotations

# Memory note: macOS Anaconda deadlocks when transformers' TF backend is
# imported unnecessarily. Force USE_TF=0 before any downstream import that
# might touch transformers.Trainer (data.utils and friends pull this chain).
import os
os.environ.setdefault("USE_TF", "0")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
CASES_DIRS = [
    TESTS_ROOT / "synthetic",
    TESTS_ROOT / "golden" / "real",
    TESTS_ROOT / "regression",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Call the real Opus Vision API instead of reading cached responses.",
    )
    parser.addoption(
        "--prompt",
        action="store",
        default="v1",
        help="Prompt version to load (e.g. v1, v2). Matches prompts/scan_<v>.md.",
    )


# ---------------------------------------------------------------------------
# Case discovery
# ---------------------------------------------------------------------------

@dataclass
class Case:
    """Immutable test-case descriptor loaded from a sibling JSON."""
    image_path: Path
    json_path: Path
    lab_chain: str
    layout: str
    quality_tier: str
    age: Optional[int]
    sex: Optional[str]
    gt_values: Dict[str, float]
    gt_units: Dict[str, str]
    gt_ref_ranges: Dict[str, Any]
    collected_at: Optional[str]
    notes: str
    degradations: list

    @property
    def id(self) -> str:
        return self.json_path.stem


def _iter_case_jsons():
    for base in CASES_DIRS:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.json")):
            if p.name.endswith(".cache.json") or ".cache." in p.name:
                continue
            yield p


def _load_case(json_path: Path) -> Case:
    data = json.loads(json_path.read_text())
    image_rel = data["image"]
    image_path = (json_path.parent / image_rel).resolve()
    patient = data.get("patient") or {}
    return Case(
        image_path=image_path,
        json_path=json_path,
        lab_chain=data.get("lab_chain", ""),
        layout=data.get("layout", ""),
        quality_tier=data.get("quality_tier", ""),
        age=patient.get("age"),
        sex=patient.get("sex"),
        gt_values={k: float(v) for k, v in (data.get("ground_truth_values") or {}).items()},
        gt_units=data.get("ground_truth_units") or {},
        gt_ref_ranges=data.get("ground_truth_ref_ranges") or {},
        collected_at=data.get("ground_truth_collected_at"),
        notes=data.get("notes", ""),
        degradations=data.get("degradations") or [],
    )


@pytest.fixture(scope="session")
def all_cases() -> list:
    return [_load_case(p) for p in _iter_case_jsons()]


# ---------------------------------------------------------------------------
# Opus client: cached / live
# ---------------------------------------------------------------------------

class OpusClient:
    """Thin facade over `api.scan._call_opus_vision` with a file cache.

    Cache location: `<image>.cache.<prompt_version>.json`, always next to the
    image. Each cache entry stores the **raw JSON the model returned**
    (already parsed), plus latency & cost metadata.
    """

    def __init__(self, live: bool, prompt_version: str):
        self.live = live
        self.prompt_version = prompt_version

    # --- public API ---

    def extract(self, image_path: Path) -> Dict[str, Any]:
        cache_path = self._cache_path(image_path)
        if not self.live and cache_path.exists():
            return json.loads(cache_path.read_text())
        if not self.live:
            pytest.skip(
                f"No cached Opus response for {image_path.name} "
                f"(prompt={self.prompt_version}). Re-run with --live to populate."
            )
        return self._live_extract(image_path, cache_path)

    # --- internals ---

    def _cache_path(self, image_path: Path) -> Path:
        stem = image_path.stem
        suffix = f".cache.{self.prompt_version}.json"
        return image_path.parent / f"{stem}{suffix}"

    def _live_extract(self, image_path: Path, cache_path: Path) -> Dict[str, Any]:
        # Deferred imports so the cached-only path doesn't drag FastAPI / anthropic.
        from api.scan import _call_opus_vision, _load_prompt, _parse_with_retry

        media_type = _guess_media_type(image_path)
        prompt = _load_prompt(self.prompt_version)
        image_bytes = image_path.read_bytes()
        try:
            parsed, latency_ms, cost = _parse_with_retry(image_bytes, media_type, prompt)
        except Exception as exc:
            pytest.fail(f"Live Opus call failed for {image_path}: {exc}")

        record = {
            "parsed": parsed,
            "latency_ms": latency_ms,
            "cost_estimate_usd": cost,
        }
        cache_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        return record


def _guess_media_type(path: Path) -> str:
    s = path.suffix.lower()
    if s in (".jpg", ".jpeg"):
        return "image/jpeg"
    if s == ".png":
        return "image/png"
    if s == ".webp":
        return "image/webp"
    if s == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


@pytest.fixture(scope="session")
def opus_client(request: pytest.FixtureRequest) -> OpusClient:
    return OpusClient(
        live=bool(request.config.getoption("--live")),
        prompt_version=str(request.config.getoption("--prompt")),
    )


# ---------------------------------------------------------------------------
# Reference ranges (shared, loaded once per session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def lab_norms() -> Dict[str, Any]:
    return json.loads(
        (TESTS_ROOT.parents[1] / "config" / "lab_norms.json").read_text()
    )
