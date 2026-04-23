"""POST /scan — Opus 4.7 Vision OCR for Polish morfologia reports.

Thin wrapper that:
  1. decodes the frontend data-URL payload into bytes + media type,
  2. loads a versioned prompt from prompts/scan_v*.md,
  3. calls the Anthropic Messages API with a vision block,
  4. retries exactly once with a decimal-separator clarification if JSON parsing
     fails or most values don't look numeric,
  5. normalises the raw JSON via api.normalizer,
  6. appends a PHI-stripped run record to tests/vision/runs/<UTC-date>.jsonl.

The heavy numeric / string correctness logic lives in api.normalizer and is
unit-tested independently. This file deliberately stays thin.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.normalizer import (
    ScanResponse,
    normalize_opus_response,
    parse_number_pl,
    strip_phi,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
RUNS_DIR = REPO_ROOT / "tests" / "vision" / "runs"

# Model ID used for requests. Bump together with the anthropic SDK version.
DEFAULT_MODEL_ID = os.getenv("BLOODAI_MODEL_ID", "claude-opus-4-7")

# Rough cost estimate in USD per input/output token (for logging only).
# Update when Anthropic publishes new prices. These are loose guardrails.
_COST_PER_MTOK_IN = 15.0
_COST_PER_MTOK_OUT = 75.0


# ---------------------------------------------------------------------------
# API schema (frontend contract)
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    imageDataUrl: str
    hint: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None


# Mirrors frontend/src/types/api.ts::ScanResponse
class ScanResponseModel(BaseModel):
    values: Dict[str, float] = {}
    confidence: Dict[str, float] = {}
    rawText: Optional[str] = None
    collectedAt: Optional[str] = None


# ---------------------------------------------------------------------------
# Prompt versioning
# ---------------------------------------------------------------------------

def _load_prompt(version: str = "v1") -> str:
    """Load the active OCR prompt from prompts/scan_<version>.md.

    The file is a Markdown document with a header section; the actual prompt
    starts after the first `---` separator on its own line. Falls back to the
    entire file if no separator is present.
    """
    path = PROMPTS_DIR / f"scan_{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    text = path.read_text()
    parts = re.split(r"^\s*---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    if len(parts) >= 2:
        return parts[-1].strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Data-URL decoding
# ---------------------------------------------------------------------------

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<payload>.+)$", re.DOTALL)


def _decode_data_url(data_url: str) -> Tuple[bytes, str]:
    m = _DATA_URL_RE.match(data_url or "")
    if not m:
        raise HTTPException(status_code=400, detail="Invalid image data URL")
    mime = m.group("mime").strip()
    try:
        body = base64.b64decode(m.group("payload"), validate=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode base64: {exc}") from exc
    if not body:
        raise HTTPException(status_code=400, detail="Empty image payload")
    return body, mime


# ---------------------------------------------------------------------------
# Opus Vision call
# ---------------------------------------------------------------------------

def _estimate_cost(in_tok: int, out_tok: int) -> float:
    return round((in_tok / 1_000_000) * _COST_PER_MTOK_IN
                 + (out_tok / 1_000_000) * _COST_PER_MTOK_OUT, 6)


def _call_opus_vision(
    image_bytes: bytes, media_type: str, prompt: str,
) -> Tuple[str, int, float]:
    """Call Claude Vision and return (raw_text, latency_ms, cost_usd_estimate).

    Raises RuntimeError if the SDK isn't installed or the API key is missing.
    The caller is responsible for JSON-decoding the returned text.
    """
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK not installed. Run `pip install -U anthropic` "
            "and ensure the version supports Claude 4.7 Vision."
        ) from exc
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    client = Anthropic(api_key=api_key)
    is_pdf = media_type == "application/pdf"
    content_block: Dict[str, Any] = (
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        }
        if is_pdf else
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        }
    )

    t0 = time.perf_counter()
    resp = client.messages.create(
        model=DEFAULT_MODEL_ID,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [content_block, {"type": "text", "text": prompt}],
        }],
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # The Messages API returns a list of content blocks.
    text_parts = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    raw_text = "".join(text_parts).strip()

    in_tok = getattr(getattr(resp, "usage", None), "input_tokens", 0) or 0
    out_tok = getattr(getattr(resp, "usage", None), "output_tokens", 0) or 0
    cost = _estimate_cost(in_tok, out_tok)
    return raw_text, latency_ms, cost


# ---------------------------------------------------------------------------
# Retry heuristic
# ---------------------------------------------------------------------------

def _looks_non_numeric(parsed: Any) -> bool:
    """Return True when more than half of the parameter values in `parsed`
    fail to parse as numbers. Triggers a decimal-separator clarification retry.
    """
    if not isinstance(parsed, dict):
        return True
    params = parsed.get("parameters") or []
    if not isinstance(params, list) or not params:
        return False
    bad = 0
    for p in params:
        if not isinstance(p, dict):
            bad += 1
            continue
        if parse_number_pl(p.get("value")) is None:
            bad += 1
    return bad > len(params) // 2


def _parse_with_retry(
    image_bytes: bytes, media_type: str, prompt: str,
) -> Tuple[Dict[str, Any], int, float]:
    """Single retry strategy: one shot, then one more with an added clarification."""
    raw, latency_ms, cost = _call_opus_vision(image_bytes, media_type, prompt)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if parsed is None or _looks_non_numeric(parsed):
        clarified = (
            prompt
            + "\n\nCLARIFY: Polish lab sheets use the comma ','. as the decimal separator. "
            "When emitting JSON, convert `14,2` to the number 14.2 (float). "
            "Return a bare JSON object — no Markdown fences, no commentary."
        )
        raw2, latency_ms2, cost2 = _call_opus_vision(image_bytes, media_type, clarified)
        latency_ms += latency_ms2
        cost += cost2
        try:
            parsed = json.loads(raw2)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Opus returned non-JSON after retry: {exc.msg}",
            ) from exc
    return parsed, latency_ms, cost


# ---------------------------------------------------------------------------
# Run logging
# ---------------------------------------------------------------------------

def _log_run(
    image_sha: str,
    extracted_stripped: Any,
    normalized: ScanResponse,
    latency_ms: int,
    cost_usd: float,
    prompt_version: str,
    model_id: str,
) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    path = RUNS_DIR / f"{date}.jsonl"
    record = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "prompt_version": prompt_version,
        "model_id": model_id,
        "image_sha": image_sha,
        "extracted": extracted_stripped,
        "values": normalized.get("values"),
        "confidence": normalized.get("confidence"),
        "latency_ms": latency_ms,
        "cost_estimate_usd": cost_usd,
    }
    with path.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------

scan_router = APIRouter()


@scan_router.post("/scan", response_model=ScanResponseModel)
async def scan_endpoint(req: ScanRequest) -> ScanResponseModel:
    """Extract structured lab values from an image / PDF of a morfologia sheet."""
    # Lazy-load the norms DB so this module can be imported without I/O.
    from data.utils import load_lab_norms
    norms_path = REPO_ROOT / "config" / "lab_norms.json"
    lab_norms = load_lab_norms(norms_path)

    img_bytes, media_type = _decode_data_url(req.imageDataUrl)
    image_sha = hashlib.sha256(img_bytes).hexdigest()

    prompt_version = os.getenv("BLOODAI_PROMPT_VERSION", "v1")
    prompt = _load_prompt(prompt_version)

    try:
        parsed, latency_ms, cost = _parse_with_retry(img_bytes, media_type, prompt)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # network, SDK, anything else
        logger.exception("Opus Vision call failed")
        raise HTTPException(status_code=502, detail=f"Opus Vision error: {exc}") from exc

    normalized = normalize_opus_response(parsed, req.age, req.sex, lab_norms)
    stripped = strip_phi(parsed)
    _log_run(
        image_sha=image_sha,
        extracted_stripped=stripped,
        normalized=normalized,
        latency_ms=latency_ms,
        cost_usd=cost,
        prompt_version=prompt_version,
        model_id=DEFAULT_MODEL_ID,
    )
    return ScanResponseModel(
        values=normalized.get("values", {}),
        confidence=normalized.get("confidence", {}),
        rawText=normalized.get("rawText"),
        collectedAt=normalized.get("collectedAt"),
    )


__all__ = [
    "scan_router",
    "ScanRequest",
    "ScanResponseModel",
    "_load_prompt",
    "_decode_data_url",
    "_call_opus_vision",
    "_parse_with_retry",
    "_log_run",
]
