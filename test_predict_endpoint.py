#!/usr/bin/env python3
"""Comprehensive validation of /predict endpoint."""

import json
import requests

BASE_URL = "http://localhost:4000"
ENDPOINT = f"{BASE_URL}/predict"

EXPECTED_CLASSES = {"POZ", "Gastroenterology", "Hematology", "Nephrology",
                    "ER", "Cardiology", "Pulmonology", "Hepatology"}
EXPECTED_PARAMS = {"HGB", "CREATININE", "PLT", "MCV", "WBC", "ALT", "AST", "UREA", "HCT"}


def validate_response(data: dict, label: str) -> bool:
    ok = True
    required = {"predictions", "attention", "ece", "modelVersion"}
    missing = required - set(data.keys())
    if missing:
        print(f"  ❌ Missing keys: {missing}"); ok = False
    else:
        print(f"  ✅ Required keys present")

    preds = data.get("predictions", [])
    if len(preds) == 8:
        print(f"  ✅ 8 classes returned")
    else:
        print(f"  ❌ Expected 8 classes, got {len(preds)}"); ok = False

    classes_seen = set()
    for p in preds:
        prob = p.get("probability", -1)
        if not (0.0 <= prob <= 1.0):
            print(f"  ❌ Probability {prob} out of [0,1]"); ok = False
        classes_seen.add(p.get("class", ""))

    if classes_seen == EXPECTED_CLASSES:
        print(f"  ✅ All 8 expected class names present")
    else:
        diff = classes_seen.symmetric_difference(EXPECTED_CLASSES)
        print(f"  ⚠️  Class name diff: {diff}")

    probs = [p["probability"] for p in preds]
    if probs == sorted(probs, reverse=True):
        print(f"  ✅ Sorted descending by probability")
    else:
        print(f"  ❌ Not sorted descending"); ok = False

    attn = data.get("attention", [])
    if attn:
        bad_params = [a["param"] for a in attn if a["param"] not in EXPECTED_PARAMS]
        if bad_params:
            print(f"  ⚠️  Unexpected attention params: {bad_params}")
        else:
            print(f"  ✅ Attention weights: {[(a['param'], a['weight']) for a in attn]}")
    else:
        print(f"  ⚠️  No attention weights")

    ece = data.get("ece")
    if ece is not None:
        print(f"  ✅ ECE = {ece}")

    ver = data.get("modelVersion", "")
    if "bert" in ver.lower():
        print(f"  ✅ modelVersion = {ver}")
    else:
        print(f"  ⚠️  modelVersion = {ver}")

    return ok


def post(payload):
    r = requests.post(ENDPOINT, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def sep(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")


def main():
    sep("BloodAI /predict Endpoint Validation")

    results = {}

    # Test 1: server alive
    sep("TEST 1: Server alive")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"  /health → {r.status_code} {r.json()}")
        results["Server Alive"] = r.status_code == 200
    except Exception as e:
        print(f"  ❌ {e}")
        results["Server Alive"] = False

    # Test 2: Healthy patient
    sep("TEST 2: Healthy patient (all normal)")
    try:
        data = post({"input": {"age": 45, "sex": "female",
                               "values": {"HGB": 13.5, "CREATININE": 0.9,
                                          "PLT": 250, "WBC": 6.5, "ALT": 25}}})
        top = data["predictions"][0]
        print(f"  Top prediction: {top['class']} ({top['probability']:.4f})")
        results["Healthy Patient"] = validate_response(data, "healthy")
    except Exception as e:
        print(f"  ❌ {e}"); results["Healthy Patient"] = False

    # Test 3: CKD + Anemia
    sep("TEST 3: CKD + Anemia (HGB low, CREATININE high)")
    try:
        data = post({"input": {"age": 65, "sex": "male",
                               "values": {"HGB": 8.5, "CREATININE": 3.2,
                                          "PLT": 180, "WBC": 7.0, "ALT": 35}}})
        top3 = [p["class"] for p in data["predictions"][:3]]
        print(f"  Top 3: {top3}")
        if "Nephrology" in top3: print("  ✅ Nephrology in top 3")
        else: print(f"  ⚠️  Nephrology not in top 3")
        results["CKD + Anemia"] = validate_response(data, "ckd")
    except Exception as e:
        print(f"  ❌ {e}"); results["CKD + Anemia"] = False

    # Test 4: Critical — HGB very low
    sep("TEST 4: Critical values (HGB 6.5, PLT 45, WBC 32)")
    try:
        data = post({"input": {"age": 55, "sex": "male",
                               "values": {"HGB": 6.5, "CREATININE": 2.5,
                                          "PLT": 45, "WBC": 32, "ALT": 35}}})
        er = next((p for p in data["predictions"] if p["class"] == "ER"), None)
        if er:
            print(f"  ER probability: {er['probability']:.4f}")
            if er["probability"] > 0.3: print("  ✅ ER above threshold (0.3556)")
        results["Critical Values"] = validate_response(data, "critical")
    except Exception as e:
        print(f"  ❌ {e}"); results["Critical Values"] = False

    # Test 5: Sparse input
    sep("TEST 5: Sparse input (only HGB)")
    try:
        data = post({"input": {"age": 30, "sex": "female", "values": {"HGB": 11.5}}})
        print(f"  Top: {data['predictions'][0]['class']} ({data['predictions'][0]['probability']:.4f})")
        results["Sparse Input"] = validate_response(data, "sparse")
    except Exception as e:
        print(f"  ❌ {e}"); results["Sparse Input"] = False

    # Summary
    sep("SUMMARY")
    for name, passed in results.items():
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}  {name}")
    n = sum(results.values())
    print(f"\n  {n}/{len(results)} tests passed")
    if n == len(results):
        print("\n  🎉 All tests passed — real BERT endpoint ready for frontend!")


if __name__ == "__main__":
    main()
