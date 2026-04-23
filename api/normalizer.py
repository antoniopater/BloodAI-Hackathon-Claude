"""Pure-function normalizer for Opus Vision OCR output.

Converts the raw JSON Claude returns (per `prompts/scan_v1.md`) into the
`ScanResponse` shape the frontend expects, normalising Polish decimal
separators, unit drift, name synonyms, and reference-range strings.

Design rules:
- No I/O. The reference-range DB is passed in as a dict (loaded by the
  FastAPI startup handler via `data.utils.load_lab_norms`).
- Deterministic. Given the same inputs, produces the same output.
- Defensive. Never raises on malformed Opus output — unknown params
  are silently dropped so the frontend keeps working.

The frontend contract lives at `frontend/src/types/api.ts` (`ScanResponse`):
    { values: Partial<Record<LabParam, number>>,
      confidence: Partial<Record<LabParam, number>>,
      rawText?: string,
      collectedAt?: string }
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple, TypedDict

from data.utils import get_age_group


# ---------------------------------------------------------------------------
# Canonical schema
# ---------------------------------------------------------------------------

CANONICAL: Tuple[str, ...] = (
    "HGB", "CREATININE", "PLT", "MCV", "WBC", "ALT", "AST", "UREA",
)

# Canonical unit per parameter (what the frontend and lab_norms.json assume).
CANONICAL_UNITS: Dict[str, str] = {
    "HGB": "g/dL",
    "CREATININE": "mg/dL",
    "PLT": "K/uL",
    "MCV": "fL",
    "WBC": "K/uL",
    "ALT": "U/L",
    "AST": "U/L",
    "UREA": "mg/dL",
}

# Polish + English aliases → canonical. Compared case-insensitively.
SYNONYMS: Dict[str, str] = {
    "hgb": "HGB",
    "hb": "HGB",
    "hemoglobin": "HGB",
    "hemoglobina": "HGB",

    "wbc": "WBC",
    "white blood cells": "WBC",
    "leukocyty": "WBC",
    "leukocyte": "WBC",
    "białe": "WBC",
    "biale krwinki": "WBC",

    "plt": "PLT",
    "platelets": "PLT",
    "płytki": "PLT",
    "plytki": "PLT",
    "trombocyty": "PLT",

    "mcv": "MCV",
    "średnia objętość krwinki": "MCV",
    "srednia objetosc krwinki": "MCV",

    "creatinine": "CREATININE",
    "kreatynina": "CREATININE",

    "urea": "UREA",
    "mocznik": "UREA",
    "bun": "UREA",
    "blood urea nitrogen": "UREA",

    "alt": "ALT",
    "alat": "ALT",
    "alt (gpt)": "ALT",
    "gpt": "ALT",

    "ast": "AST",
    "aspat": "AST",
    "asat": "AST",
    "ast (got)": "AST",
    "got": "AST",
}

# Numeric mapping for Opus's textual confidence.
_CONF_MAP: Dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}


# ---------------------------------------------------------------------------
# ScanResponse TypedDict
# ---------------------------------------------------------------------------

class ScanResponse(TypedDict, total=False):
    values: Dict[str, float]
    confidence: Dict[str, float]
    rawText: Optional[str]
    collectedAt: Optional[str]


# ---------------------------------------------------------------------------
# Number / range parsing
# ---------------------------------------------------------------------------

# Matches Polish numeric literals: optional sign, optional <|>, digits with
# thin-space / regular-space / non-breaking-space thousands, comma or dot
# decimal separator.
_NUMBER_RE = re.compile(
    r"""
    ^\s*
    (?:(?P<bound>[<>≤≥])\s*)?           # optional inequality (kept out of the value)
    (?P<sign>[+-])?                     # optional sign
    (?P<int>\d{1,3}(?:[   \s]\d{3})*|\d+)   # thousands grouped by space
    (?:[.,](?P<frac>\d+))?              # decimal separator , or .
    \s*$
    """,
    re.VERBOSE,
)


def parse_number_pl(raw: Any) -> Optional[float]:
    """Parse a Polish-formatted number.

    Accepts: "14,2", "14.2", "1 234,5", "<5", "> 4", " 3,14 ".
    Returns the numeric value as float; for "<5" returns 5.0 (the caller
    loses the inequality — that's intentional for downstream consumers that
    treat values atomically). Returns None when the string is not a number.

    Non-string numeric inputs pass through (float(3) == 3.0).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):  # bool is an int subclass — exclude
        return None
    if isinstance(raw, (int, float)):
        f = float(raw)
        if f != f:  # NaN
            return None
        return f
    if not isinstance(raw, str):
        return None

    m = _NUMBER_RE.match(raw)
    if not m:
        return None

    int_part = m.group("int")
    # Strip any inner whitespace (regular, thin, non-breaking)
    int_part = re.sub(r"[   \s]", "", int_part)
    frac = m.group("frac") or ""
    sign = m.group("sign") or ""
    literal = f"{sign}{int_part}" + (f".{frac}" if frac else "")
    try:
        return float(literal)
    except ValueError:
        return None


# Accepts: "80-100", "80–100" (en dash), "80—100" (em dash), "80 do 100",
# "<100", "> 4", "≤ 50", "≥ 3.5"
_RANGE_SPLIT_RE = re.compile(r"\s*(?:[-–—]|do)\s*")


def parse_ref_range(raw: Any) -> Tuple[Optional[float], Optional[float]]:
    """Parse a reference range string into (low, high).

    Single-sided: "<100" → (None, 100), ">4" → (4, None).
    Two-sided: "80-100", "80–100", "80 do 100" → (80, 100).
    """
    if raw is None:
        return (None, None)
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return (parse_number_pl(raw[0]), parse_number_pl(raw[1]))
    if not isinstance(raw, str):
        return (None, None)

    s = raw.strip()
    if not s:
        return (None, None)

    # Single-sided
    if s.startswith("<") or s.startswith("≤"):
        n = parse_number_pl(s.lstrip("<≤ ").strip())
        return (None, n)
    if s.startswith(">") or s.startswith("≥"):
        n = parse_number_pl(s.lstrip(">≥ ").strip())
        return (n, None)

    parts = _RANGE_SPLIT_RE.split(s, maxsplit=1)
    if len(parts) == 2:
        return (parse_number_pl(parts[0]), parse_number_pl(parts[1]))

    # Single number → treat as upper bound "absolute".
    n = parse_number_pl(s)
    return (n, n) if n is not None else (None, None)


def fallback_ref_range(
    param: str, age: Optional[int], sex: Optional[str], norms_db: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float]]:
    """Look up reference range from lab_norms.json when the sheet didn't
    print one (or the OCR couldn't read it). Uses data.utils.get_age_group
    for bucketing.

    Falls back to adult/female if age or sex is missing — conservative for
    most lab values. Returns (None, None) when the parameter is unknown.
    """
    param_up = param.upper()
    if param_up not in norms_db:
        return (None, None)
    norms = norms_db[param_up]
    age_group = get_age_group(age) if isinstance(age, int) else "under_60"
    sex_key = (sex or "f").lower()[:1]
    if sex_key not in ("m", "f"):
        sex_key = "f"
    bucket = norms.get(age_group, {}).get(sex_key) or {}
    return (bucket.get("low"), bucket.get("high"))


# ---------------------------------------------------------------------------
# Name + unit normalization
# ---------------------------------------------------------------------------

def _strip_diacritics(s: str) -> str:
    # Light normalization: lowercase, strip parenthesised qualifiers, collapse ws.
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def canonicalize_name(raw: Any) -> Optional[str]:
    """Map a printed field name to the canonical LabParam code."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    key = _strip_diacritics(raw)
    # Try exact synonym
    if key in SYNONYMS:
        return SYNONYMS[key]
    # Try stripping qualifiers like "ALT (GPT)" → "alt"
    short = re.sub(r"\s*\([^)]*\)\s*", "", key).strip()
    if short in SYNONYMS:
        return SYNONYMS[short]
    # Try canonical-code direct match (upper)
    up = raw.strip().upper()
    if up in CANONICAL:
        return up
    return None


def _norm_unit(u: Any) -> str:
    if not isinstance(u, str):
        return ""
    u = u.strip().lower()
    # Unicode micro / small-mu → ASCII 'u'.
    u = u.replace("µ", "u").replace("μ", "u").replace("µ", "u").replace("μ", "u")
    # Superscript digits → regular.
    u = u.translate(str.maketrans({"¹": "1", "²": "2", "³": "3", "⁶": "6", "⁹": "9", "⁰": "0"}))
    # Strip all internal whitespace and the leading "x".
    u = re.sub(r"\s+", "", u)
    if u.startswith("x"):
        u = u[1:]
    return u


def convert_unit(param: str, value: float, unit: Any) -> Tuple[float, str]:
    """Convert `(value, unit)` for `param` to the canonical unit.

    Unknown units are left alone and the canonical unit is reported anyway —
    the normalizer does not fabricate conversions. Callers rely on
    `CANONICAL_UNITS[param]` as the always-returned string.
    """
    canonical = CANONICAL_UNITS.get(param, "")
    u = _norm_unit(unit)

    # Already canonical (any casing / spacing variant).
    if u == _norm_unit(canonical):
        return value, canonical
    if u == "":
        return value, canonical

    if param == "HGB":
        if u in ("g/l",):
            return value / 10.0, "g/dL"
        if u in ("mmol/l",):
            # 1 mmol/L Hb ≈ 1.611 g/dL
            return value * 1.611, "g/dL"
    elif param in ("WBC", "PLT"):
        # K/uL == 10^3/µL == 10^9/L numerically.
        if u in ("10^9/l", "10e9/l", "g/l", "g/l", "10*9/l"):
            return value, "K/uL"
        if u in ("10^3/ul", "10e3/ul", "10*3/ul", "tys/ul", "tys./ul"):
            return value, "K/uL"
        # Indian labs report WBC/PLT in cells/µL (same as /cumm): 6220 → 6.22 K/uL
        if u in ("/cumm", "/ul", "cells/ul", "cells/cumm", "cells/microl", "/microl"):
            if value > 500:
                return value / 1000.0, "K/uL"
    elif param == "CREATININE":
        if u == "umol/l":
            return value / 88.4, "mg/dL"
    elif param == "UREA":
        # Polish labs: "mocznik" in mg/dL (range ~15–50) OR as BUN mg/dL (7–20).
        # lab_norms.json uses BUN. mmol/L urea → BUN mg/dL: ×2.801.
        if u == "mmol/l":
            return value * 2.801, "mg/dL"
        if u == "g/l":
            return value * 100.0, "mg/dL"
    elif param == "MCV":
        if u in ("um^3", "um3"):
            return value, "fL"  # 1 fL = 1 µm³

    # Unit we don't recognise — keep the value, report canonical unit so
    # downstream code sees a predictable field. The test suite's
    # `unit_swap_rate` metric is the safety net here.
    return value, canonical


# ---------------------------------------------------------------------------
# PHI stripping
# ---------------------------------------------------------------------------

# A conservative heuristic: 9–13 consecutive digits looks like a PESEL or a
# similar national ID and gets redacted. We deliberately redact both in the
# notes free-text and in any free-text patient field.
_PESEL_RE = re.compile(r"\b\d{9,13}\b")

_PHI_KEYS = {
    "name", "first_name", "firstname", "last_name", "lastname",
    "full_name", "patient_name", "imię", "nazwisko",
    "pesel", "pesel_id", "nid", "ssn",
    "dob", "date_of_birth", "birth_date", "data_urodzenia",
    "address", "adres", "phone", "telefon", "email", "e-mail",
}


def strip_phi(raw_json: Any) -> Any:
    """Return a copy of raw_json with likely-PHI fields removed.

    Scope (deliberately narrow — we don't want to mangle legitimate nested
    fields like `parameters[].name`):
      * top-level keys matching _PHI_KEYS are dropped;
      * under `patient`, keys matching _PHI_KEYS are dropped;
      * long digit runs (9–13 digits, PESEL-like) inside any top-level string
        value (e.g. `notes`) are replaced with "[REDACTED]".
    Strings passed directly get their digit runs redacted too. Other inputs
    pass through unchanged. Input is never mutated.
    """
    if isinstance(raw_json, str):
        return _PESEL_RE.sub("[REDACTED]", raw_json)
    if isinstance(raw_json, dict):
        out: Dict[str, Any] = {}
        for k, v in raw_json.items():
            if k.lower() in _PHI_KEYS:
                continue
            if k == "patient" and isinstance(v, dict):
                out[k] = {
                    pk: pv for pk, pv in v.items() if pk.lower() not in _PHI_KEYS
                }
                continue
            if isinstance(v, str):
                out[k] = _PESEL_RE.sub("[REDACTED]", v)
            else:
                out[k] = v
        return out
    if isinstance(raw_json, list):
        return [strip_phi(item) if isinstance(item, str) else item for item in raw_json]
    return raw_json


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def normalize_opus_response(
    raw: Any,
    age: Optional[int],
    sex: Optional[str],
    norms_db: Dict[str, Any],
) -> ScanResponse:
    """Convert an Opus Vision JSON response into a ScanResponse dict.

    `raw` is expected to follow the shape produced by prompts/scan_v1.md:
        {
          "patient": {"age": int|null, "sex": "m"|"f"|null},
          "lab_name": str|null,
          "parameters": [
            {"name": "HGB", "value": 14.2, "unit": "g/dL",
             "reference_low": 12.0, "reference_high": 17.5, "source": "from_sheet"},
            ...
          ],
          "confidence": "high"|"medium"|"low",
          "notes": str|null
        }

    Defensive: missing parameters are skipped (not raised), unknown names are
    dropped. Overall confidence (top-level string) is spread to each parameter
    unless the parameter object carries its own `confidence` field.
    """
    values: Dict[str, float] = {}
    confidence: Dict[str, float] = {}

    if not isinstance(raw, dict):
        return {"values": values, "confidence": confidence}

    overall_conf_raw = raw.get("confidence", "medium")
    if isinstance(overall_conf_raw, str):
        overall_conf = _CONF_MAP.get(overall_conf_raw.strip().lower(), 0.6)
    elif isinstance(overall_conf_raw, (int, float)):
        overall_conf = float(overall_conf_raw)
    else:
        overall_conf = 0.6

    params = raw.get("parameters") or []
    if not isinstance(params, list):
        params = []

    for p in params:
        if not isinstance(p, dict):
            continue
        canonical = canonicalize_name(p.get("name"))
        if canonical is None:
            continue
        num = parse_number_pl(p.get("value"))
        if num is None:
            continue
        converted_value, _ = convert_unit(canonical, num, p.get("unit"))
        values[canonical] = round(converted_value, 4)

        p_conf = p.get("confidence")
        if isinstance(p_conf, str):
            confidence[canonical] = _CONF_MAP.get(p_conf.strip().lower(), overall_conf)
        elif isinstance(p_conf, (int, float)):
            confidence[canonical] = float(p_conf)
        else:
            confidence[canonical] = overall_conf

    result: ScanResponse = {"values": values, "confidence": confidence}

    raw_text = raw.get("rawText")
    if isinstance(raw_text, str) and raw_text:
        result["rawText"] = raw_text

    collected = raw.get("collected_at") or raw.get("collectedAt")
    if isinstance(collected, str) and collected:
        result["collectedAt"] = collected

    # The `age` / `sex` / `norms_db` arguments are kept in the signature so the
    # endpoint can opportunistically enrich the response with fallback ranges
    # (handled at the endpoint layer, not here — keeps this fn pure for tests).
    _ = (age, sex, norms_db)
    return result


__all__ = [
    "CANONICAL",
    "CANONICAL_UNITS",
    "SYNONYMS",
    "ScanResponse",
    "parse_number_pl",
    "parse_ref_range",
    "fallback_ref_range",
    "canonicalize_name",
    "convert_unit",
    "strip_phi",
    "normalize_opus_response",
]
