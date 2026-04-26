#!/usr/bin/env python3
"""
A/B/C test: do the new 52 questions (many with out-of-vocab tokens) help BERT?

For each clinical case we call /predict three times:
  A. baseline — no symptom_tokens
  B. KNOWN tokens — only tokens present in BERT vocab
  C. UNKNOWN tokens — tokens added in the new 52-question set that are NOT in vocab

Reports per-case max |Δ| vs baseline, then a final verdict on whether the
unknown tokens add any real value.
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional

import requests

BASE_URL = "http://localhost:4000"
PREDICT_URL = f"{BASE_URL}/predict"
HEALTH_URL = f"{BASE_URL}/health"
TIMEOUT = 30


# ─── Test cases ───────────────────────────────────────────────
# known_tokens use ONLY the 12 vocab-confirmed symptoms.
# unknown_tokens use OOV strings introduced by the new 52-question set.
TEST_CASES = [
    {
        "name": "65M CKD + anemia",
        "base": {"age": 65, "sex": "male",
                 "values": {"HGB": 8.5, "CREATININE": 3.2, "PLT": 180}},
        "known":   ["symptom_edema_yes", "symptom_dyspnea_yes"],
        "unknown": ["symptom_dehydration_yes", "symptom_nephrotoxic_med_yes"],
    },
    {
        "name": "45F mild anemia (microcytic)",
        "base": {"age": 45, "sex": "female",
                 "values": {"HGB": 10.5, "MCV": 65, "CREATININE": 0.9}},
        "known":   ["symptom_easy_bruising_yes", "symptom_heavy_periods_yes"],
        "unknown": ["symptom_poor_nutrition_yes", "symptom_iron_deficiency_risk_yes"],
    },
    {
        "name": "55M liver injury",
        "base": {"age": 55, "sex": "male",
                 "values": {"ALT": 180, "AST": 150, "HGB": 14.0}},
        "known":   ["symptom_jaundice_yes", "symptom_stomach_pain_yes"],
        "unknown": ["symptom_substance_abuse_yes", "symptom_hepatotoxic_medication_yes"],
    },
    {
        "name": "50M critical pancytopenia",
        "base": {"age": 50, "sex": "male",
                 "values": {"HGB": 6.5, "PLT": 45, "WBC": 32}},
        "known":   ["symptom_easy_bruising_yes", "symptom_dyspnea_yes", "symptom_gi_bleed_yes"],
        "unknown": ["symptom_infection_yes", "symptom_immunosuppression_yes"],
    },
    {
        "name": "70F senior GI bleed",
        "base": {"age": 70, "sex": "female",
                 "values": {"HGB": 7.5, "PLT": 120, "CREATININE": 1.8}},
        "known":   ["symptom_gi_bleed_yes", "symptom_weight_loss_yes"],
        "unknown": ["symptom_antiplatelet_anticoagulant_yes", "symptom_fall_risk_yes"],
    },
    {
        "name": "35F normal labs + chest pain",
        "base": {"age": 35, "sex": "female",
                 "values": {"HGB": 13.5, "CREATININE": 0.9}},
        "known":   ["symptom_chest_pain_yes", "symptom_dyspnea_yes"],
        "unknown": ["symptom_acute_illness_yes", "symptom_immune_response_yes"],
    },
    {
        "name": "40M UTI symptoms",
        "base": {"age": 40, "sex": "male",
                 "values": {"HGB": 14.0, "CREATININE": 1.0, "WBC": 7.5}},
        "known":   ["symptom_dysuria_yes", "symptom_hematuria_yes"],
        "unknown": ["symptom_urinary_symptoms_yes", "symptom_kidney_disease_risk_yes"],
    },
]


def call_predict(base: dict, tokens: Optional[List[str]]) -> Optional[dict]:
    payload = {"input": {**base}}
    if tokens:
        payload["input"]["symptom_tokens"] = tokens
    try:
        r = requests.post(PREDICT_URL, json=payload, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"  ! request error: {exc}")
        return None
    if r.status_code != 200:
        print(f"  ! HTTP {r.status_code}: {r.text[:160]}")
        return None
    return r.json()


def probs(result: dict) -> Dict[str, float]:
    return {p["class"]: p["probability"] for p in result.get("predictions", [])}


def deltas(base_probs: Dict[str, float], variant_probs: Dict[str, float]) -> Dict[str, float]:
    return {cls: variant_probs[cls] - base_probs.get(cls, 0.0) for cls in variant_probs}


def health() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        if r.status_code == 200:
            print(f"  /health → {r.json()}")
            return True
    except requests.RequestException as exc:
        print(f"  cannot reach {BASE_URL}: {exc}")
    return False


def fmt_top_deltas(d: Dict[str, float], n: int = 3) -> str:
    top = sorted(d.items(), key=lambda kv: abs(kv[1]), reverse=True)[:n]
    return ", ".join(f"{cls}={v:+.3f}" for cls, v in top)


def run_case(case: dict) -> Optional[Dict[str, float]]:
    name = case["name"]
    base = case["base"]
    known = case["known"]
    unknown = case["unknown"]

    print(f"\n{'=' * 78}")
    print(f"  {name}")
    print(f"{'=' * 78}")
    print(f"  baseline labs: {base['values']}")
    print(f"  known tokens:   {known}")
    print(f"  unknown tokens: {unknown}")

    res_base = call_predict(base, None)
    res_known = call_predict(base, known)
    res_unk = call_predict(base, unknown)
    if not (res_base and res_known and res_unk):
        return None

    p_base = probs(res_base)
    p_known = probs(res_known)
    p_unk = probs(res_unk)

    d_known = deltas(p_base, p_known)
    d_unk = deltas(p_base, p_unk)

    max_known = max(abs(v) for v in d_known.values())
    max_unk = max(abs(v) for v in d_unk.values())

    print(f"\n  KNOWN  (vs baseline)  max|Δ|={max_known:.4f}   top: {fmt_top_deltas(d_known)}")
    print(f"  UNKNOWN(vs baseline)  max|Δ|={max_unk:.4f}   top: {fmt_top_deltas(d_unk)}")

    ratio = max_known / max(max_unk, 1e-6)
    if max_known > 2 * max_unk and max_known > 0.05:
        verdict = f"  🟢 KNOWN clearly stronger ({ratio:.1f}× unknown)"
    elif max_unk > 2 * max_known and max_unk > 0.05:
        verdict = f"  🔴 unexpected — unknown stronger ({1/ratio:.1f}× known)"
    elif max_known < 0.01 and max_unk < 0.01:
        verdict = "  ⚪ both negligible"
    else:
        verdict = "  🟡 similar magnitude"
    print(verdict)

    return {"known": max_known, "unknown": max_unk}


def main() -> None:
    print(f"\n{'=' * 78}")
    print(f"  BloodAI · 52-Question Token Validation (KNOWN vs UNKNOWN tokens)")
    print(f"{'=' * 78}\n")

    print("Health check:")
    if not health():
        print('  Start backend: USE_TF=0 PYTHONPATH="." uvicorn api.main:app --port 4000')
        sys.exit(1)

    rows: List[Dict[str, float]] = []
    for case in TEST_CASES:
        r = run_case(case)
        if r:
            rows.append(r)

    if not rows:
        print("\nNo cases completed.")
        sys.exit(1)

    avg_known = sum(r["known"] for r in rows) / len(rows)
    avg_unk = sum(r["unknown"] for r in rows) / len(rows)
    max_known = max(r["known"] for r in rows)
    max_unk = max(r["unknown"] for r in rows)

    print(f"\n\n{'=' * 78}")
    print(f"  AGGREGATE")
    print(f"{'=' * 78}")
    print(f"  KNOWN tokens   (in vocab):      avg max|Δ| = {avg_known:.4f}, top {max_known:.4f}")
    print(f"  UNKNOWN tokens (OOV → [UNK]):   avg max|Δ| = {avg_unk:.4f}, top {max_unk:.4f}")
    print(f"  ratio known/unknown            = {avg_known / max(avg_unk, 1e-6):.1f}×")

    print(f"\n  {'-' * 60}")
    if avg_known > 0.05 and avg_unk < 0.01:
        print("  ✅ Confirmed: only the 12 vocab tokens move predictions.")
        print("     Unknown tokens are dead weight for BERT — but still useful")
        print("     for UX (history, audit). Keep all 52 questions; no model harm.")
    elif avg_unk > 0.01:
        print("  🟡 Surprising — unknown tokens have some effect (subword effects?).")
        print("     Worth investigating; full removal not justified.")
    else:
        print("  🔴 Even known tokens barely move predictions — adaptive Q's may be")
        print("     redundant for this model. Consider removing them entirely.")
    print(f"  {'-' * 60}\n")


if __name__ == "__main__":
    main()
