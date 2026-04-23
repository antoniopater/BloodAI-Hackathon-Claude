"""End-to-end Vision harness.

Each parametrised test case is one image + its JSON ground truth. In the
default (cached) mode, the Opus response is read from a sibling cache file
written by a prior `--live` run. Cases without a cache skip — that's the
designed-in safety net so running `pytest` in CI never burns API tokens.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from api.normalizer import normalize_opus_response
from tests.vision.conftest import Case, _iter_case_jsons, _load_case
from tests.vision.metrics import (
    TOLERANCES,
    exact_match_rate,
    fuzzy_match,
    unit_swap_rate,
)

TESTS_ROOT = Path(__file__).resolve().parent


def _discover_cases() -> List[Case]:
    return [_load_case(p) for p in _iter_case_jsons()]


# ---------------------------------------------------------------------------
# Per-case correctness
# ---------------------------------------------------------------------------

_ALL_CASES = _discover_cases()


@pytest.mark.parametrize("case", _ALL_CASES, ids=lambda c: c.id)
def test_extraction_meets_tolerance(case: Case, opus_client, lab_norms):
    assert case.image_path.exists(), f"Image missing on disk: {case.image_path}"

    record = opus_client.extract(case.image_path)
    parsed = record.get("parsed") if "parsed" in record else record
    normalized = normalize_opus_response(parsed, case.age, case.sex, lab_norms)

    matches = fuzzy_match(normalized["values"], case.gt_values)
    failures = {k: v for k, v in matches.items() if not v}
    if failures:
        pytest.fail(
            "Field-level tolerance breach on "
            f"{case.id}: failed={sorted(failures)}. "
            f"pred={normalized['values']} gt={case.gt_values} "
            f"(tol={ {k: TOLERANCES.get(k, 0) for k in failures} })"
        )


# ---------------------------------------------------------------------------
# Aggregate checks
# ---------------------------------------------------------------------------

def _collect_all(opus_client, lab_norms) -> tuple[list, list]:
    preds, gts = [], []
    for case in _ALL_CASES:
        if not case.image_path.exists():
            continue
        try:
            record = opus_client.extract(case.image_path)
        except pytest.skip.Exception:
            continue
        parsed = record.get("parsed") if "parsed" in record else record
        normalized = normalize_opus_response(parsed, case.age, case.sex, lab_norms)
        preds.append(normalized["values"])
        gts.append(case.gt_values)
    return preds, gts


def test_aggregate_unit_swap_rate_below_threshold(opus_client, lab_norms):
    preds, gts = _collect_all(opus_client, lab_norms)
    if not preds:
        pytest.skip("No cached responses available.")
    us = unit_swap_rate(preds, gts)
    assert us < 0.01, f"unit_swap_rate too high: {us:.3f}"


def test_aggregate_exact_match_rate_above_threshold(opus_client, lab_norms):
    preds, gts = _collect_all(opus_client, lab_norms)
    if not preds:
        pytest.skip("No cached responses available.")
    per_doc = [exact_match_rate(p, g) for p, g in zip(preds, gts)]
    mean_emr = sum(per_doc) / len(per_doc)
    assert mean_emr >= 0.85, f"mean EMR too low: {mean_emr:.3f}"


# ---------------------------------------------------------------------------
# The harness itself must collect at least the 5 mandatory synthetic seeds.
# (This guards against someone accidentally deleting the generator output.)
# ---------------------------------------------------------------------------

def test_minimum_synthetic_seeds_present():
    synthetic = TESTS_ROOT / "synthetic"
    seeds = [p for p in synthetic.glob("seed_*.png") if not p.name.endswith(".cache.png")]
    assert len(seeds) >= 5, (
        "At least 5 seed fixtures must exist — regenerate with "
        "`python tests/vision/synthetic/generate.py`."
    )
