"""Metrics for the Vision validation harness.

Keeps dependencies light (numpy + jiwer only) so the metrics module can be
imported without dragging in torch. The ECE implementation mirrors the math
in `model.evaluate.compute_ece` — see that module for the canonical
2D-multi-label version.

Tolerances below express per-parameter acceptable absolute error. They are
motivated by clinical significance (e.g., 0.1 g/dL for hemoglobin is well
under the typical analytical CV of 1 %) and by OCR rounding noise.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np


TOLERANCES: Dict[str, float] = {
    "HGB": 0.1,
    "WBC": 0.1,
    "PLT": 5.0,
    "MCV": 1.0,
    "CREATININE": 0.05,
    "ALT": 2.0,
    "AST": 2.0,
    "UREA": 1.0,
}


# ---------------------------------------------------------------------------
# Field-level correctness
# ---------------------------------------------------------------------------

def _iter_params(*dicts: Mapping[str, Any]) -> Iterable[str]:
    seen = set()
    for d in dicts:
        for k in d:
            if k not in seen:
                seen.add(k)
                yield k


def fuzzy_match(
    pred: Mapping[str, float],
    gt: Mapping[str, float],
    tol: Optional[Mapping[str, float]] = None,
) -> Dict[str, bool]:
    """Per-parameter boolean match within absolute tolerance.

    Returns a dict keyed by parameter. A parameter missing in `pred` but
    present in `gt` counts as a miss (False); missing in both is excluded
    from the result.
    """
    tol = tol or TOLERANCES
    out: Dict[str, bool] = {}
    for param in _iter_params(pred, gt):
        if param not in gt:
            # We don't penalise extractions beyond ground truth; the harness
            # treats those as "extra" and reports precision separately.
            continue
        if param not in pred:
            out[param] = False
            continue
        p = float(pred[param])
        g = float(gt[param])
        allow = float(tol.get(param, 0.0))
        out[param] = abs(p - g) <= allow
    return out


def exact_match_rate(
    pred: Mapping[str, float],
    gt: Mapping[str, float],
    tol: Optional[Mapping[str, float]] = None,
) -> float:
    """Fraction of ground-truth fields matched within tolerance (per document).

    If `gt` is empty, returns 1.0 (vacuously true — no fields to miss).
    """
    if not gt:
        return 1.0
    matches = fuzzy_match(pred, gt, tol)
    return sum(matches.values()) / max(len(matches), 1)


def per_field_prf1(
    preds: Sequence[Mapping[str, float]],
    gts: Sequence[Mapping[str, float]],
    tol: Optional[Mapping[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """Per-parameter Precision / Recall / F1 across a batch of documents.

    Precision = (#correct extractions) / (#extractions).
    Recall    = (#correct extractions) / (#ground-truth occurrences).
    """
    if len(preds) != len(gts):
        raise ValueError("preds and gts must be the same length")
    tol = tol or TOLERANCES

    all_params = set()
    for p in preds:
        all_params.update(p.keys())
    for g in gts:
        all_params.update(g.keys())

    out: Dict[str, Dict[str, float]] = {}
    for param in sorted(all_params):
        tp = fp = fn = 0
        allow = float(tol.get(param, 0.0))
        for p, g in zip(preds, gts):
            has_p = param in p
            has_g = param in g
            if has_p and has_g:
                if abs(float(p[param]) - float(g[param])) <= allow:
                    tp += 1
                else:
                    fp += 1
                    fn += 1
            elif has_p and not has_g:
                fp += 1
            elif has_g and not has_p:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[param] = {"P": precision, "R": recall, "F1": f1, "TP": tp, "FP": fp, "FN": fn}
    return out


# ---------------------------------------------------------------------------
# Text-level CER (raw OCR body, if present)
# ---------------------------------------------------------------------------

def cer(pred_text: str, gt_text: str) -> float:
    """Character Error Rate via jiwer when available, falling back to a
    Levenshtein implementation so the metric stays usable without extra deps.
    """
    if not gt_text:
        return 0.0 if not pred_text else 1.0
    try:
        import jiwer  # type: ignore
        return float(jiwer.cer(gt_text, pred_text))
    except Exception:
        # Fallback: classic Wagner-Fischer edit distance / len(gt).
        return _levenshtein(pred_text, gt_text) / len(gt_text)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        row = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            row[j] = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + cost)
        prev = row
    return prev[-1]


# ---------------------------------------------------------------------------
# Expected Calibration Error for scalar confidences
# ---------------------------------------------------------------------------

def ece(
    confidences: Sequence[float],
    correct: Sequence[bool],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error for a stream of (confidence, correct) pairs.

    Mirrors `model.evaluate.compute_ece` but collapses the multi-label case to
    1D: each sample contributes one confidence and one boolean correctness.
    Zero-weight bins are skipped.
    """
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    if not confidences:
        return 0.0

    c = np.clip(np.asarray(confidences, dtype=float), 0.0, 1.0)
    y = np.asarray([bool(x) for x in correct], dtype=float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(c)
    ece_val = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (c >= lo) & (c < hi) if hi < 1.0 else (c >= lo) & (c <= hi)
        weight = mask.mean()
        if weight == 0.0:
            continue
        avg_conf = c[mask].mean()
        acc = y[mask].mean()
        ece_val += weight * abs(avg_conf - acc)
    return float(ece_val)


# ---------------------------------------------------------------------------
# Unit-swap detection: did the model return a value that looks ×10 or ÷10 off?
# ---------------------------------------------------------------------------

def unit_swap_rate(
    preds: Sequence[Mapping[str, float]],
    gts: Sequence[Mapping[str, float]],
    tol: Optional[Mapping[str, float]] = None,
) -> float:
    """Fraction of (param, document) pairs where the prediction matches
    ground truth only after multiplying or dividing by 10 within tolerance.
    A high rate points at unit confusion (g/dL ↔ g/L etc.).
    """
    if len(preds) != len(gts):
        raise ValueError("preds and gts must be the same length")
    tol = tol or TOLERANCES
    total = swaps = 0
    for p, g in zip(preds, gts):
        for param, gt_value in g.items():
            if param not in p:
                continue
            total += 1
            p_val = float(p[param])
            gt_val = float(gt_value)
            allow = float(tol.get(param, 0.0))
            if abs(p_val - gt_val) <= allow:
                continue
            if abs(p_val / 10.0 - gt_val) <= allow or abs(p_val * 10.0 - gt_val) <= allow:
                swaps += 1
    return (swaps / total) if total else 0.0


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------

def latency_p95(latencies_ms: Sequence[float]) -> float:
    """95th percentile latency in ms. Returns 0.0 for an empty input."""
    if not latencies_ms:
        return 0.0
    return float(np.percentile(np.asarray(latencies_ms, dtype=float), 95))


# ---------------------------------------------------------------------------
# Aggregate a run JSONL log into a summary dict.
# ---------------------------------------------------------------------------

def summarize(run_jsonl: Path) -> Dict[str, Any]:
    """Read a `tests/vision/runs/*.jsonl` file and return aggregate metrics.

    Expects each line to be a run record (see api.scan._log_run). Records
    without an `evaluation` block are counted under `calls` but excluded
    from accuracy statistics.
    """
    run_jsonl = Path(run_jsonl)
    if not run_jsonl.exists():
        return {"calls": 0, "note": f"No run file at {run_jsonl}"}

    calls = 0
    latencies: List[float] = []
    costs: List[float] = []
    preds: List[Dict[str, float]] = []
    gts: List[Dict[str, float]] = []
    conf_vals: List[float] = []
    conf_correct: List[bool] = []

    with run_jsonl.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            calls += 1
            lat = rec.get("latency_ms")
            if isinstance(lat, (int, float)):
                latencies.append(float(lat))
            cost = rec.get("cost_estimate_usd")
            if isinstance(cost, (int, float)):
                costs.append(float(cost))
            ev = rec.get("evaluation") or {}
            pred = ev.get("pred_values")
            gt = ev.get("gt_values")
            if isinstance(pred, dict) and isinstance(gt, dict):
                preds.append(pred)
                gts.append(gt)
                conf = rec.get("confidence") or {}
                matches = fuzzy_match(pred, gt)
                for param, ok in matches.items():
                    if param in conf:
                        conf_vals.append(float(conf[param]))
                        conf_correct.append(bool(ok))

    if preds:
        prf1 = per_field_prf1(preds, gts)
        emr = float(np.mean([exact_match_rate(p, g) for p, g in zip(preds, gts)]))
        us = unit_swap_rate(preds, gts)
        ece_val = ece(conf_vals, conf_correct) if conf_vals else None
    else:
        prf1, emr, us, ece_val = {}, None, None, None

    return {
        "calls": calls,
        "latency_p95_ms": latency_p95(latencies),
        "total_cost_usd": float(sum(costs)),
        "exact_match_rate": emr,
        "per_field_prf1": prf1,
        "unit_swap_rate": us,
        "ece": ece_val,
    }


__all__ = [
    "TOLERANCES",
    "fuzzy_match",
    "exact_match_rate",
    "per_field_prf1",
    "cer",
    "ece",
    "unit_swap_rate",
    "latency_p95",
    "summarize",
]
