"""Unit tests for api.normalizer.

These tests run fully offline — no API, no files (except the bundled
config/lab_norms.json loaded once via data.utils.load_lab_norms).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.normalizer import (
    CANONICAL_UNITS,
    canonicalize_name,
    convert_unit,
    fallback_ref_range,
    normalize_opus_response,
    parse_number_pl,
    parse_ref_range,
    strip_phi,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LAB_NORMS = json.loads((REPO_ROOT / "config" / "lab_norms.json").read_text())


# ---------------------------------------------------------------------------
# parse_number_pl
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("14,2", 14.2),
        ("14.2", 14.2),
        (" 3,14 ", 3.14),
        ("0,5", 0.5),
        ("1 234,5", 1234.5),  # regular space thousands
        ("1 234,5", 1234.5),  # non-breaking space thousands
        ("1 234,5", 1234.5),  # narrow no-break space
        ("<5", 5.0),
        ("> 4", 4.0),
        ("≤ 50", 50.0),
        ("+42", 42.0),
        ("-3,1", -3.1),
        (14.2, 14.2),
        (7, 7.0),
    ],
)
def test_parse_number_pl_valid(raw, expected):
    assert parse_number_pl(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "abc", None, True, False, "N/A", "—"])
def test_parse_number_pl_invalid(raw):
    assert parse_number_pl(raw) is None


# ---------------------------------------------------------------------------
# parse_ref_range
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("80-100", (80.0, 100.0)),
        ("80–100", (80.0, 100.0)),      # en dash
        ("80—100", (80.0, 100.0)),      # em dash
        ("80 - 100", (80.0, 100.0)),
        ("80 do 100", (80.0, 100.0)),
        ("12,0 - 16,0", (12.0, 16.0)),
        ("<100", (None, 100.0)),
        ("> 4", (4.0, None)),
        ("≤ 50", (None, 50.0)),
        ("≥ 3,5", (3.5, None)),
        ([12.0, 16.0], (12.0, 16.0)),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_ref_range(raw, expected):
    low, high = parse_ref_range(raw)
    exp_low, exp_high = expected
    if exp_low is None:
        assert low is None
    else:
        assert low == pytest.approx(exp_low)
    if exp_high is None:
        assert high is None
    else:
        assert high == pytest.approx(exp_high)


# ---------------------------------------------------------------------------
# canonicalize_name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("HGB", "HGB"),
        ("hgb", "HGB"),
        ("Hemoglobina", "HGB"),
        ("hemoglobin", "HGB"),
        ("WBC", "WBC"),
        ("Leukocyty", "WBC"),
        ("LEUKOCYTY", "WBC"),
        ("PLT", "PLT"),
        ("Płytki", "PLT"),
        ("Trombocyty", "PLT"),
        ("MCV", "MCV"),
        ("Kreatynina", "CREATININE"),
        ("creatinine", "CREATININE"),
        ("Mocznik", "UREA"),
        ("BUN", "UREA"),
        ("ALT", "ALT"),
        ("ALAT", "ALT"),
        ("ALT (GPT)", "ALT"),
        ("alt (gpt)", "ALT"),
        ("AST", "AST"),
        ("ASPAT", "AST"),
        ("AST (GOT)", "AST"),
    ],
)
def test_canonicalize_name_known(raw, expected):
    assert canonicalize_name(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "UNKNOWN_PARAM", 123, True])
def test_canonicalize_name_unknown(raw):
    assert canonicalize_name(raw) is None


# ---------------------------------------------------------------------------
# convert_unit
# ---------------------------------------------------------------------------

def test_convert_unit_identity_hgb():
    v, u = convert_unit("HGB", 14.2, "g/dL")
    assert v == pytest.approx(14.2)
    assert u == "g/dL"


def test_convert_unit_hgb_g_per_L_to_g_per_dL():
    v, u = convert_unit("HGB", 140.0, "g/L")
    assert v == pytest.approx(14.0)
    assert u == "g/dL"


def test_convert_unit_wbc_10e9_per_L_identity():
    v, u = convert_unit("WBC", 6.8, "10^9/L")
    assert v == pytest.approx(6.8)
    assert u == "K/uL"


def test_convert_unit_plt_superscript():
    v, u = convert_unit("PLT", 250.0, "10³/µL")
    assert v == pytest.approx(250.0)
    assert u == "K/uL"


def test_convert_unit_creatinine_umol_to_mg():
    # 88.4 umol/L should normalize to ~1.0 mg/dL
    v, u = convert_unit("CREATININE", 88.4, "µmol/L")
    assert v == pytest.approx(1.0, rel=1e-3)
    assert u == "mg/dL"


def test_convert_unit_urea_mmol_to_mg():
    v, u = convert_unit("UREA", 5.0, "mmol/L")
    # BUN conversion factor ≈ 2.801
    assert v == pytest.approx(14.005, rel=1e-3)
    assert u == "mg/dL"


def test_convert_unit_unknown_returns_canonical_unit():
    # Unknown unit: we don't fabricate a conversion, but the unit label
    # returned is always the canonical one so downstream code is predictable.
    v, u = convert_unit("HGB", 14.2, "wibble")
    assert v == 14.2
    assert u == CANONICAL_UNITS["HGB"]


def test_convert_unit_mcv_um3_to_fL():
    v, u = convert_unit("MCV", 88.0, "µm³")
    assert v == pytest.approx(88.0)
    assert u == "fL"


# ---------------------------------------------------------------------------
# strip_phi
# ---------------------------------------------------------------------------

def test_strip_phi_removes_patient_name_and_pesel():
    raw = {
        "patient": {
            "name": "Jan Kowalski",
            "pesel": "92010112345",
            "age": 33,
            "sex": "m",
        },
        "parameters": [{"name": "HGB", "value": 14.2}],
        "notes": "PESEL 92010112345 attached",
    }
    out = strip_phi(raw)
    assert "name" not in out["patient"]
    assert "pesel" not in out["patient"]
    assert out["patient"]["age"] == 33
    assert out["patient"]["sex"] == "m"
    assert "92010112345" not in out["notes"]
    assert "[REDACTED]" in out["notes"]
    # Non-PHI passes through intact
    assert out["parameters"] == [{"name": "HGB", "value": 14.2}]


def test_strip_phi_is_non_mutating():
    raw = {"patient": {"name": "Jan", "age": 33}}
    _ = strip_phi(raw)
    assert raw["patient"]["name"] == "Jan"


def test_strip_phi_handles_non_dict():
    assert strip_phi(None) is None
    assert strip_phi("plain string 12345678901 inside") == "plain string [REDACTED] inside"
    # Lists of dicts pass through — PHI stripping is scoped to the top-level
    # dict + the `patient` subtree, on purpose (so `parameters[].name`
    # survives). PESEL-looking strings inside the list are still redacted.
    assert strip_phi([{"name": "A"}, {"age": 5}]) == [{"name": "A"}, {"age": 5}]
    assert strip_phi(["plain 12345678901 here", "ok"]) == [
        "plain [REDACTED] here",
        "ok",
    ]


# ---------------------------------------------------------------------------
# fallback_ref_range
# ---------------------------------------------------------------------------

def test_fallback_ref_range_uses_age_group():
    low, high = fallback_ref_range("HGB", 45, "m", LAB_NORMS)
    assert low == pytest.approx(13.5)
    assert high == pytest.approx(17.5)


def test_fallback_ref_range_kids_bucket():
    low, high = fallback_ref_range("HGB", 10, "f", LAB_NORMS)
    assert low == pytest.approx(11.0)
    assert high == pytest.approx(14.5)


def test_fallback_ref_range_missing_age_defaults_to_under_60():
    low, high = fallback_ref_range("HGB", None, "m", LAB_NORMS)
    assert low == pytest.approx(13.5)
    assert high == pytest.approx(17.5)


def test_fallback_ref_range_unknown_param():
    assert fallback_ref_range("WIBBLE", 45, "m", LAB_NORMS) == (None, None)


# ---------------------------------------------------------------------------
# normalize_opus_response — happy path + defensive
# ---------------------------------------------------------------------------

_RAW_OK = {
    "patient": {"age": 42, "sex": "m"},
    "lab_name": "ALAB",
    "parameters": [
        {"name": "Hemoglobina", "value": "14,2", "unit": "g/dL",
         "reference_low": "13,5", "reference_high": "17,5", "source": "from_sheet"},
        {"name": "Leukocyty", "value": 6.8, "unit": "10^9/L"},
        {"name": "Kreatynina", "value": "88,4", "unit": "µmol/L"},
    ],
    "confidence": "high",
    "notes": "OK",
}


def test_normalize_happy_path():
    out = normalize_opus_response(_RAW_OK, 42, "m", LAB_NORMS)
    assert out["values"]["HGB"] == pytest.approx(14.2)
    assert out["values"]["WBC"] == pytest.approx(6.8)
    assert out["values"]["CREATININE"] == pytest.approx(1.0, rel=1e-3)
    # All three confidences mirror "high" → 0.9
    for p in ("HGB", "WBC", "CREATININE"):
        assert out["confidence"][p] == pytest.approx(0.9)


def test_normalize_unit_swap_detected_for_hgb():
    raw = {
        "parameters": [{"name": "HGB", "value": 140.0, "unit": "g/L"}],
        "confidence": "medium",
    }
    out = normalize_opus_response(raw, 42, "m", LAB_NORMS)
    assert out["values"]["HGB"] == pytest.approx(14.0)


def test_normalize_drops_unknown_param():
    raw = {
        "parameters": [
            {"name": "HGB", "value": 14.2, "unit": "g/dL"},
            {"name": "WIBBLEGLUCOSE", "value": 90, "unit": "mg/dL"},
        ],
        "confidence": "medium",
    }
    out = normalize_opus_response(raw, 42, "m", LAB_NORMS)
    assert "HGB" in out["values"]
    assert "WIBBLEGLUCOSE" not in out["values"]


def test_normalize_skips_unparseable_value():
    raw = {
        "parameters": [
            {"name": "HGB", "value": "not-a-number", "unit": "g/dL"},
            {"name": "WBC", "value": None, "unit": "K/uL"},
            {"name": "PLT", "value": "230", "unit": "K/uL"},
        ],
        "confidence": "low",
    }
    out = normalize_opus_response(raw, 42, "m", LAB_NORMS)
    assert "HGB" not in out["values"]
    assert "WBC" not in out["values"]
    assert out["values"]["PLT"] == pytest.approx(230)
    assert out["confidence"]["PLT"] == pytest.approx(0.3)


def test_normalize_per_param_confidence_overrides_overall():
    raw = {
        "parameters": [
            {"name": "HGB", "value": 14.2, "unit": "g/dL", "confidence": "low"},
            {"name": "WBC", "value": 6.8, "unit": "K/uL"},
        ],
        "confidence": "high",
    }
    out = normalize_opus_response(raw, 42, "m", LAB_NORMS)
    assert out["confidence"]["HGB"] == pytest.approx(0.3)
    assert out["confidence"]["WBC"] == pytest.approx(0.9)


def test_normalize_defensive_on_malformed_input():
    # None, empty dict, missing parameters array, non-list parameters
    assert normalize_opus_response(None, 42, "m", LAB_NORMS) == {"values": {}, "confidence": {}}
    assert normalize_opus_response({}, 42, "m", LAB_NORMS) == {"values": {}, "confidence": {}}
    assert normalize_opus_response({"parameters": "not a list"}, 42, "m", LAB_NORMS) == {
        "values": {},
        "confidence": {},
    }


def test_normalize_carries_rawtext_and_collectedat():
    raw = {
        "parameters": [{"name": "HGB", "value": 14.2, "unit": "g/dL"}],
        "confidence": "high",
        "rawText": "HGB 14,2 g/dL",
        "collected_at": "2025-03-11",
    }
    out = normalize_opus_response(raw, 42, "m", LAB_NORMS)
    assert out["rawText"] == "HGB 14,2 g/dL"
    assert out["collectedAt"] == "2025-03-11"


def test_normalize_polish_decimal_comma_floor():
    # "14,2" must parse as 14.2, not 142.
    raw = {
        "parameters": [{"name": "HGB", "value": "14,2", "unit": "g/dL"}],
        "confidence": "high",
    }
    out = normalize_opus_response(raw, 42, "m", LAB_NORMS)
    assert out["values"]["HGB"] == pytest.approx(14.2)
    assert out["values"]["HGB"] < 20.0  # regression guard
