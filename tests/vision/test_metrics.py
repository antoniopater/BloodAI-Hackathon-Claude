"""Sanity tests for tests.vision.metrics.

Zero external API. numpy + (optional) jiwer only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.vision.metrics import (
    TOLERANCES,
    cer,
    ece,
    exact_match_rate,
    fuzzy_match,
    latency_p95,
    per_field_prf1,
    summarize,
    unit_swap_rate,
)


def test_fuzzy_match_within_tolerance():
    pred = {"HGB": 14.25, "WBC": 6.79, "PLT": 232}
    gt   = {"HGB": 14.2,  "WBC": 6.8,  "PLT": 230}
    m = fuzzy_match(pred, gt)
    assert m == {"HGB": True, "WBC": True, "PLT": True}


def test_fuzzy_match_outside_tolerance():
    pred = {"HGB": 14.5}
    gt   = {"HGB": 14.2}
    assert fuzzy_match(pred, gt) == {"HGB": False}


def test_fuzzy_match_missing_in_pred_is_false():
    assert fuzzy_match({}, {"HGB": 14.2}) == {"HGB": False}


def test_fuzzy_match_extra_in_pred_is_excluded():
    # Predictions beyond the GT are not penalised here — precision handles it.
    assert fuzzy_match({"HGB": 14.2, "EXTRA": 1.0}, {"HGB": 14.2}) == {"HGB": True}


def test_exact_match_rate_all_correct():
    pred = {"HGB": 14.2, "WBC": 6.8}
    gt   = {"HGB": 14.2, "WBC": 6.8}
    assert exact_match_rate(pred, gt) == 1.0


def test_exact_match_rate_half_correct():
    pred = {"HGB": 14.2, "WBC": 12.0}
    gt   = {"HGB": 14.2, "WBC": 6.8}
    assert exact_match_rate(pred, gt) == pytest.approx(0.5)


def test_exact_match_rate_empty_gt_is_vacuous():
    assert exact_match_rate({}, {}) == 1.0


def test_per_field_prf1_perfect():
    preds = [{"HGB": 14.2, "WBC": 6.8}] * 3
    gts   = [{"HGB": 14.2, "WBC": 6.8}] * 3
    out = per_field_prf1(preds, gts)
    for param in ("HGB", "WBC"):
        assert out[param]["P"] == 1.0
        assert out[param]["R"] == 1.0
        assert out[param]["F1"] == 1.0


def test_per_field_prf1_missing_counts_as_fn():
    preds = [{"HGB": 14.2}, {"HGB": 14.2}]
    gts   = [{"HGB": 14.2, "WBC": 6.8}, {"HGB": 14.2, "WBC": 6.8}]
    out = per_field_prf1(preds, gts)
    # WBC: 2 FN, 0 TP → recall 0
    assert out["WBC"]["R"] == 0.0
    assert out["WBC"]["FN"] == 2


def test_per_field_prf1_length_mismatch_raises():
    with pytest.raises(ValueError):
        per_field_prf1([{}], [{}, {}])


def test_cer_identical():
    assert cer("HGB 14,2 g/dL", "HGB 14,2 g/dL") == 0.0


def test_cer_fully_wrong():
    assert cer("xxxxx", "HGB 14,2 g/dL") > 0.5


def test_ece_perfect_calibration():
    # Confidence 1.0 when correct, 0.0 when wrong → perfectly calibrated.
    assert ece([1.0, 1.0, 0.0, 0.0], [True, True, False, False]) == pytest.approx(0.0)


def test_ece_always_overconfident():
    # Confidence 0.9 across the board, only half are correct → |0.9 - 0.5| = 0.4.
    val = ece([0.9] * 10, [True] * 5 + [False] * 5, n_bins=10)
    assert val == pytest.approx(0.4, abs=0.01)


def test_ece_empty_returns_zero():
    assert ece([], []) == 0.0


def test_ece_length_mismatch_raises():
    with pytest.raises(ValueError):
        ece([0.9], [True, False])


def test_unit_swap_rate_detects_x10():
    # HGB: ground truth 14.2; model returned 142 (forgot g/L→g/dL). That's a swap.
    preds = [{"HGB": 142.0}]
    gts   = [{"HGB": 14.2}]
    assert unit_swap_rate(preds, gts) == pytest.approx(1.0)


def test_unit_swap_rate_ignores_exact_match():
    preds = [{"HGB": 14.2}]
    gts   = [{"HGB": 14.2}]
    assert unit_swap_rate(preds, gts) == 0.0


def test_unit_swap_rate_genuine_error_is_not_flagged():
    # Off by +2 → neither ×10 nor ÷10 → NOT a unit swap.
    preds = [{"HGB": 16.2}]
    gts   = [{"HGB": 14.2}]
    assert unit_swap_rate(preds, gts) == 0.0


def test_latency_p95_and_empty():
    assert latency_p95([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]) >= 900
    assert latency_p95([]) == 0.0


def test_summarize_round_trip(tmp_path: Path):
    run = tmp_path / "runs.jsonl"
    lines = [
        {
            "latency_ms": 2500, "cost_estimate_usd": 0.03,
            "confidence": {"HGB": 0.9, "WBC": 0.9},
            "evaluation": {
                "pred_values": {"HGB": 14.2, "WBC": 6.8},
                "gt_values":   {"HGB": 14.2, "WBC": 6.8},
            },
        },
        {
            "latency_ms": 4000, "cost_estimate_usd": 0.04,
            "confidence": {"HGB": 0.9, "WBC": 0.6},
            "evaluation": {
                "pred_values": {"HGB": 14.0, "WBC": 10.5},
                "gt_values":   {"HGB": 14.2, "WBC": 6.8},
            },
        },
    ]
    run.write_text("\n".join(json.dumps(x) for x in lines))
    s = summarize(run)
    assert s["calls"] == 2
    assert s["latency_p95_ms"] > 3000
    assert s["exact_match_rate"] is not None
    assert 0.0 <= s["exact_match_rate"] <= 1.0
    assert "HGB" in s["per_field_prf1"]
    assert s["unit_swap_rate"] == pytest.approx(0.0)


def test_tolerances_cover_all_canonical_params():
    from api.normalizer import CANONICAL
    for p in CANONICAL:
        assert p in TOLERANCES, f"missing tolerance for {p}"
