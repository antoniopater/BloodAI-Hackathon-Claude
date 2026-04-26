#!/usr/bin/env python3
"""
A/B test: do `symptom_tokens` change BERT triage predictions?

For each case we call /predict twice with identical lab values:
  - variant A: tokens with `_yes` suffix
  - variant B: same tokens with `_no` suffix
Delta per class = P(yes) - P(no).

Only tokens present in checkpoints/finetune/tokenizer/tokenizer.json are used,
otherwise they would be tokenised as [UNK] and produce a false null result.
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional

import requests

BASE_URL = "http://localhost:4000"
PREDICT_URL = f"{BASE_URL}/predict"
HEALTH_URL = f"{BASE_URL}/health"

TIMEOUT = 30


# Symptom token prefixes that ARE in the trained tokenizer vocab.
VALID_SYMPTOM_PREFIXES = {
    "symptom_chest_pain", "symptom_dyspnea", "symptom_dysuria",
    "symptom_easy_bruising", "symptom_edema", "symptom_gi_bleed",
    "symptom_heavy_periods", "symptom_hematuria", "symptom_jaundice",
    "symptom_stomach_pain", "symptom_vomit", "symptom_weight_loss",
}


def yes(*prefixes: str) -> List[str]:
    for p in prefixes:
        assert p in VALID_SYMPTOM_PREFIXES, f"{p} is not in vocab"
    return [f"{p}_yes" for p in prefixes]


def no(*prefixes: str) -> List[str]:
    for p in prefixes:
        assert p in VALID_SYMPTOM_PREFIXES, f"{p} is not in vocab"
    return [f"{p}_no" for p in prefixes]


TEST_CASES = [
    {
        "name": "65M CKD + anemia (NEFRO)",
        "input": {"age": 65, "sex": "male",
                  "values": {"HGB": 8.5, "CREATININE": 3.2, "PLT": 180, "WBC": 7.5, "ALT": 35}},
        "prefixes": ["symptom_edema", "symptom_dyspnea", "symptom_hematuria"],
    },
    {
        "name": "45F mild anemia (HEMATO)",
        "input": {"age": 45, "sex": "female",
                  "values": {"HGB": 10.5, "CREATININE": 0.9, "PLT": 250, "WBC": 6.0, "ALT": 25}},
        "prefixes": ["symptom_dyspnea", "symptom_easy_bruising", "symptom_heavy_periods"],
    },
    {
        "name": "55M liver injury (HEPATO)",
        "input": {"age": 55, "sex": "male",
                  "values": {"HGB": 14.0, "CREATININE": 1.0, "PLT": 200, "WBC": 8.0, "ALT": 180, "AST": 150}},
        "prefixes": ["symptom_jaundice", "symptom_stomach_pain", "symptom_vomit"],
    },
    {
        "name": "50M critical (SOR)",
        "input": {"age": 50, "sex": "male",
                  "values": {"HGB": 6.5, "CREATININE": 2.5, "PLT": 45, "WBC": 32, "ALT": 35}},
        "prefixes": ["symptom_gi_bleed", "symptom_easy_bruising", "symptom_weight_loss"],
    },
    {
        "name": "35F healthy baseline (POZ)",
        "input": {"age": 35, "sex": "female",
                  "values": {"HGB": 13.5, "CREATININE": 0.9, "PLT": 250, "WBC": 6.5, "ALT": 25}},
        "prefixes": ["symptom_chest_pain", "symptom_dyspnea"],
    },
    {
        "name": "60M ambiguous mild (GASTRO?)",
        "input": {"age": 60, "sex": "male",
                  "values": {"HGB": 13.0, "CREATININE": 1.1, "PLT": 220, "WBC": 7.0, "ALT": 65, "AST": 48}},
        "prefixes": ["symptom_stomach_pain", "symptom_vomit", "symptom_weight_loss"],
    },
]


def call_predict(input_data: dict, symptom_tokens: List[str]) -> Optional[dict]:
    payload = {"input": {**input_data, "symptom_tokens": symptom_tokens}}
    try:
        r = requests.post(PREDICT_URL, json=payload, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"  ! request failed: {exc}")
        return None
    if r.status_code != 200:
        print(f"  ! HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.json()


def probs_by_class(result: dict) -> Dict[str, float]:
    return {p["class"]: p["probability"] for p in result.get("predictions", [])}


def health_check() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=5)
    except requests.RequestException as exc:
        print(f"  cannot reach {BASE_URL}: {exc}")
        return False
    if r.status_code != 200:
        print(f"  /health returned {r.status_code}")
        return False
    body = r.json()
    print(f"  /health → {body}")
    return True


def vocab_sanity_check() -> None:
    """Confirm symptom tokens actually move the needle vs a fake/unknown token."""
    base_input = {"age": 50, "sex": "male", "values": {"HGB": 12.0, "CREATININE": 1.2}}
    real = call_predict(base_input, ["symptom_edema_yes"])
    fake = call_predict(base_input, ["symptom_FAKE_TOKEN_yes"])
    if not real or not fake:
        print("  sanity check inconclusive (request failed)")
        return
    real_probs = probs_by_class(real)
    fake_probs = probs_by_class(fake)
    max_diff = max(abs(real_probs.get(k, 0) - fake_probs.get(k, 0)) for k in real_probs)
    print(f"  vocab sanity: max |Δ| between real-token and unknown-token call = {max_diff:.4f}")
    if max_diff < 1e-4:
        print("  ⚠️  even a known token has no effect — model may ignore symptoms entirely.")


def categorise(max_delta: float) -> str:
    if max_delta > 0.05: return "SIGNIFICANT"
    if max_delta > 0.01: return "MODERATE"
    if max_delta > 0.001: return "MINIMAL"
    return "NONE"


VERDICT_EMOJI = {"SIGNIFICANT": "🟢", "MODERATE": "🟡", "MINIMAL": "🟠", "NONE": "🔴"}


def run_case(case: dict) -> Optional[float]:
    name = case["name"]
    prefixes = case["prefixes"]

    print(f"\n{'=' * 72}")
    print(f"  {name}")
    print(f"  prefixes: {prefixes}")
    print(f"{'=' * 72}")

    res_yes = call_predict(case["input"], yes(*prefixes))
    res_no = call_predict(case["input"], no(*prefixes))
    if not res_yes or not res_no:
        print("  SKIP — at least one call failed.")
        return None

    p_yes = probs_by_class(res_yes)
    p_no = probs_by_class(res_no)

    deltas = {cls: p_yes[cls] - p_no.get(cls, 0.0) for cls in p_yes}
    sorted_classes = sorted(deltas, key=lambda c: abs(deltas[c]), reverse=True)

    print(f"  {'Class':<18} {'no':>8} {'yes':>8} {'Δ':>10}  {'%':>8}")
    print(f"  {'-' * 60}")
    for cls in sorted_classes:
        d = deltas[cls]
        pct = (d / p_no[cls] * 100) if p_no.get(cls, 0) > 1e-3 else 0.0
        marker = ""
        if abs(d) > 0.05: marker = "  ⚠️ SIGNIFICANT"
        elif abs(d) > 0.01: marker = "  📊"
        print(f"  {cls:<18} {p_no.get(cls, 0):>8.4f} {p_yes[cls]:>8.4f} {d:>+10.4f} {pct:>+7.1f}%{marker}")

    max_delta = max(abs(d) for d in deltas.values())
    cat = categorise(max_delta)
    print(f"\n  {VERDICT_EMOJI[cat]} {cat} (max |Δ| = {max_delta:.4f})")
    return max_delta


def main() -> None:
    print(f"\n{'=' * 72}")
    print(f"  BloodAI · Adaptive Questions Impact Test")
    print(f"  Endpoint: {PREDICT_URL}")
    print(f"{'=' * 72}\n")

    print("Health check:")
    if not health_check():
        print("\n  Start the backend first:")
        print('   USE_TF=0 PYTHONPATH="." uvicorn api.main:app --port 4000')
        sys.exit(1)

    print("\nVocab sanity check:")
    vocab_sanity_check()

    deltas: List[tuple[str, float]] = []
    for case in TEST_CASES:
        d = run_case(case)
        if d is not None:
            deltas.append((case["name"], d))

    if not deltas:
        print("\nNo cases completed.")
        sys.exit(1)

    print(f"\n\n{'=' * 72}")
    print(f"  FINAL SUMMARY")
    print(f"{'=' * 72}")

    counts = {"SIGNIFICANT": 0, "MODERATE": 0, "MINIMAL": 0, "NONE": 0}
    for _, d in deltas:
        counts[categorise(d)] += 1

    for cat in ("SIGNIFICANT", "MODERATE", "MINIMAL", "NONE"):
        print(f"  {VERDICT_EMOJI[cat]} {cat:<12} {counts[cat]}")

    avg = sum(d for _, d in deltas) / len(deltas)
    top = max(deltas, key=lambda x: x[1])
    print(f"\n  avg max |Δ|: {avg:.4f}")
    print(f"  highest:     {top[1]:.4f} — {top[0]}")

    print(f"\n  {'-' * 50}")
    if counts["SIGNIFICANT"] >= 2:
        print("  ✅ KEEP adaptive questions — symptom tokens move predictions meaningfully.")
    elif counts["SIGNIFICANT"] >= 1 or counts["MODERATE"] >= 2:
        print("  🟡 OPTIONAL — modest effect; consider hiding behind 'advanced' toggle.")
    else:
        print("  🔴 REMOVE adaptive questions — symptom tokens barely change output.")
    print(f"  {'-' * 50}\n")


if __name__ == "__main__":
    main()
