#!/usr/bin/env python3
"""
Recommended follow-up tests endpoint.

Given BERT-flagged specialties + lab values + symptom tokens, returns a
personalized list of tests the patient should consider doing BEFORE
their specialist visit, plus what to bring to the visit.
"""

from pathlib import Path
from typing import Dict, List, Optional
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "recommended_tests.json"
TESTS_CONFIG: Dict[str, dict] = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


class RecommendationRequest(BaseModel):
    age: int
    sex: str
    values: Dict[str, float]
    flags: List[str]
    symptom_tokens: Optional[List[str]] = None


class RecommendedTest(BaseModel):
    name: str
    why: str
    type: str
    nfz_covered: bool
    approx_cost_pln: int
    fasting_required: bool
    turnaround_days: int
    note: Optional[str] = None
    priority: str


class SpecialtyRecommendation(BaseModel):
    specialty: str
    display_name: str
    tests: List[RecommendedTest]
    bring_to_visit: List[str]
    urgent_note: Optional[str] = None
    total_cost_nfz: int
    total_cost_private: int


class RecommendationsResponse(BaseModel):
    recommendations: List[SpecialtyRecommendation]
    general_tips: List[str]


@router.post("/tests", response_model=RecommendationsResponse)
async def get_recommended_tests(request: RecommendationRequest):
    if not request.flags:
        raise HTTPException(status_code=400, detail="flags must contain at least one specialty")

    recommendations: List[SpecialtyRecommendation] = []

    for specialty in request.flags:
        if specialty not in TESTS_CONFIG:
            logger.info(f"Unknown specialty in flags: {specialty}")
            continue

        config = TESTS_CONFIG[specialty]
        tests: List[RecommendedTest] = []

        for test in config.get("always_recommended", []):
            tests.append(RecommendedTest(
                name=test["name"],
                why=test["why"],
                type=test["type"],
                nfz_covered=test.get("nfz_covered", True),
                approx_cost_pln=test.get("approx_cost_pln", 0),
                fasting_required=test.get("fasting_required", False),
                turnaround_days=test.get("turnaround_days", 1),
                note=test.get("note"),
                priority="must",
            ))

        for test in config.get("conditional", []):
            condition = test.get("condition", "")
            if not _evaluate_condition(condition, request.values, request.age, request.sex, request.symptom_tokens):
                continue
            tests.append(RecommendedTest(
                name=test["name"],
                why=test["why"],
                type=test["type"],
                nfz_covered=test.get("nfz_covered", True),
                approx_cost_pln=test.get("approx_cost_pln", 0),
                fasting_required=test.get("fasting_required", False),
                turnaround_days=test.get("turnaround_days", 1),
                note=test.get("note"),
                priority="recommended",
            ))

        total_private = sum(t.approx_cost_pln for t in tests)

        recommendations.append(SpecialtyRecommendation(
            specialty=specialty,
            display_name=config.get("display_name", specialty),
            tests=tests,
            bring_to_visit=config.get("bring_to_visit", []),
            urgent_note=config.get("urgent_note"),
            total_cost_nfz=0,
            total_cost_private=total_private,
        ))

    general_tips = _generate_tips(request)

    return RecommendationsResponse(
        recommendations=recommendations,
        general_tips=general_tips,
    )


def _evaluate_condition(
    condition: str,
    values: Dict[str, float],
    age: int,
    sex: str,
    symptom_tokens: Optional[List[str]],
) -> bool:
    """Rule-based evaluation of conditional test inclusion."""
    if not condition:
        return False

    cond = condition.lower()
    tokens_lower = [t.lower() for t in (symptom_tokens or [])]
    sex_norm = sex.lower()
    is_male = sex_norm in ("m", "male")

    # Lab thresholds
    if "creatinine > 3.0" in cond and values.get("CREATININE", 0) > 3.0:
        return True
    if "creatinine > 2.0" in cond and values.get("CREATININE", 0) > 2.0:
        return True
    if "creatinine > 1.5" in cond and values.get("CREATININE", 0) > 1.5:
        return True
    if "alt > 100" in cond and values.get("ALT", 0) > 100:
        return True
    if "alt elevated" in cond and values.get("ALT", 0) > 40:
        # Hemochromatosis screening: ALT elevated and male
        if "male" in cond:
            return values.get("ALT", 0) > 40 and is_male
        return values.get("ALT", 0) > 40
    if "hgb < 10" in cond and values.get("HGB", 999) < 10:
        return True
    if "wbc abnormal" in cond:
        wbc = values.get("WBC")
        if wbc is not None and (wbc < 4.0 or wbc > 11.0):
            return True
    if "plt < 100" in cond and values.get("PLT", 250) < 100:
        return True
    if "nt-probnp elevated" in cond and values.get("NT_PROBNP", 0) > 125:
        return True

    # Age / sex
    if "age > 50" in cond and age > 50:
        # Often paired with "unexplained anemia"
        if "unexplained anemia" in cond:
            hgb = values.get("HGB", 999)
            return age > 50 and hgb < 12
        return age > 50

    # Symptom-based
    if "chest_pain_yes" in cond and any("chest_pain_yes" in t for t in tokens_lower):
        return True
    if "syncope" in cond and any("syncope" in t and "yes" in t for t in tokens_lower):
        return True
    if "dyspnea" in cond and any("dyspnea" in t and "yes" in t for t in tokens_lower):
        return True
    if "palpitations" in cond and any("palpitations" in t and "yes" in t for t in tokens_lower):
        return True
    if "upper gi symptoms" in cond and any(
        any(s in t for s in ("nausea_yes", "abdominal_pain_yes", "heartburn_yes", "vomiting_yes"))
        for t in tokens_lower
    ):
        return True
    if "anemia and gi symptoms" in cond:
        anemic = values.get("HGB", 999) < 12
        gi = any(
            any(s in t for s in ("diarrhea_yes", "abdominal_pain_yes", "weight_loss_yes"))
            for t in tokens_lower
        )
        return anemic and gi

    # First-visit fallback (when no other condition matched and "first visit" present)
    if "first visit" in cond:
        return True

    return False


def _generate_tips(request: RecommendationRequest) -> List[str]:
    tips = [
        "Bring a photo ID and your insurance card (EHIC if you are from the EU)",
        "Print or photograph these recommendations and show them to your doctor",
    ]

    has_fasting = False
    for specialty in request.flags:
        cfg = TESTS_CONFIG.get(specialty)
        if not cfg:
            continue
        for test in cfg.get("always_recommended", []) + cfg.get("conditional", []):
            if test.get("fasting_required"):
                has_fasting = True
                break
        if has_fasting:
            break
    if has_fasting:
        tips.append(
            "Some tests require fasting (8–12 hours without food). "
            "It is best to book a morning appointment."
        )

    if request.age >= 65:
        tips.append(
            "Ask someone close to you to come along to the visit — two pairs of ears "
            "remember the recommendations better."
        )

    if len(request.flags) > 1:
        tips.append(
            f"You have referrals to {len(request.flags)} specialists. "
            "Start with the highest priority."
        )

    if "SOR" in request.flags:
        tips.insert(0, "⚠️ URGENT: The model detected critical values. Do not wait for further tests — go to the Emergency Department.")

    return tips
