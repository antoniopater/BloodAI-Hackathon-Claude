from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional
import json
from pathlib import Path

router = APIRouter(tags=["explain"])

_cfg = Path(__file__).parent.parent / "config"
_LAB_NORMS: dict = json.loads((_cfg / "lab_norms.json").read_text())
_MED_CTX: dict = json.loads((_cfg / "medical_context.json").read_text())
_CRITICAL = _MED_CTX["critical_thresholds"]
_COMORBIDITIES = _MED_CTX["comorbidity_patterns"]
_CKD_STAGING = _MED_CTX["creatinine_ckd_staging"]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ExplainInput(BaseModel):
    age: int = 45
    sex: str = "female"
    values: Dict[str, Optional[float]] = {}
    notes: Optional[str] = None
    collectedAt: Optional[str] = None


class TriagePredictionIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    class_: str = Field(alias="class", default="POZ")
    probability: float = 0.0


class TriageResultIn(BaseModel):
    predictions: List[TriagePredictionIn] = []
    attention: List[Dict] = []


class ExplainRequest(BaseModel):
    input: ExplainInput
    triage: Optional[TriageResultIn] = None
    mode: str = "patient"


class ExplainResponse(BaseModel):
    patientSummary: str
    clinicalSummary: Optional[str] = None
    followUpQuestions: Optional[List[str]] = None
    redFlags: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _age_group(age: int) -> str:
    if age < 18: return "kids"
    if age < 30: return "under_30"
    if age < 60: return "under_60"
    return "seniors"


def _sex_key(sex: str) -> str:
    return "m" if sex.lower() in ("m", "male") else "f"


def _get_norms(param: str, age: int, sex: str) -> Optional[dict]:
    return _LAB_NORMS.get(param, {}).get(_age_group(age), {}).get(_sex_key(sex))


def _top_class(triage: Optional[TriageResultIn]) -> str:
    if not triage or not triage.predictions:
        return "POZ"
    return max(triage.predictions, key=lambda p: p.probability).class_


def _flagged_classes(triage: Optional[TriageResultIn], threshold: float = 0.50) -> List[str]:
    if not triage:
        return ["POZ"]
    flagged = [p.class_ for p in triage.predictions if p.probability >= threshold]
    return flagged or ["POZ"]


def _ckd_stage(creatinine: float, sex: str) -> Optional[str]:
    key = "male" if _sex_key(sex) == "m" else "female"
    for row in _CKD_STAGING[key]:
        if creatinine <= row["max"]:
            return row["stage"]
    return None


# ---------------------------------------------------------------------------
# Abnormality analysis
# ---------------------------------------------------------------------------

def _analyse_abnormals(
    vals: Dict[str, Optional[float]], age: int, sex: str
) -> tuple[List[str], List[str]]:
    """Returns (patient_findings, clinical_findings)."""
    patient, clinical = [], []

    def check(param, label_patient, label_clinical_tmpl):
        v = vals.get(param)
        if v is None:
            return
        n = _get_norms(param, age, sex)
        if not n:
            return
        low, high = n["low"], n["high"]
        unit = n.get("unit", "")
        c = _CRITICAL.get(param, {})

        if v < low:
            is_critical = c.get("critical_low") is not None and v < c["critical_low"]
            prefix = "⚠️ CRITICAL: " if is_critical else ""
            patient.append(f"{prefix}{label_patient} low ({v} {unit}) — reference {low}–{high}")
            clinical.append(label_clinical_tmpl.format(v=v, low=low, high=high, unit=unit, dir="LOW"))
        elif v > high:
            is_critical = c.get("critical_high") is not None and v > c["critical_high"]
            prefix = "⚠️ CRITICAL: " if is_critical else ""
            patient.append(f"{prefix}{label_patient} high ({v} {unit}) — reference {low}–{high}")
            clinical.append(label_clinical_tmpl.format(v=v, low=low, high=high, unit=unit, dir="HIGH"))

    check("HGB",        "Haemoglobin",    "HGB {v} {unit} ({dir}; ref {low}–{high})")
    check("PLT",        "Platelets",      "PLT {v} {unit} ({dir}; ref {low}–{high})")
    check("WBC",        "White cells",    "WBC {v} {unit} ({dir}; ref {low}–{high})")
    check("CREATININE", "Creatinine",     "Creatinine {v} {unit} ({dir}; ref {low}–{high})")
    check("ALT",        "ALT (liver)",    "ALT {v} {unit} ({dir}; ref {low}–{high})")
    check("AST",        "AST (liver)",    "AST {v} {unit} ({dir}; ref {low}–{high})")
    check("MCV",        "MCV (cell size)","MCV {v} {unit} ({dir}; ref {low}–{high})")
    check("UREA",       "Urea",           "Urea {v} {unit} ({dir}; ref {low}–{high})")

    return patient, clinical


def _detect_comorbidities(vals: dict, age: int, sex: str) -> List[str]:
    notes = []

    def sev(param):
        v = vals.get(param)
        if v is None: return 0.0
        n = _get_norms(param, age, sex)
        if not n: return 0.0
        low, high = n["low"], n["high"]
        if v < low: return (low - v) / low
        if v > high: return (v - high) / high
        return 0.0

    hgb_low = sev("HGB") > 0.25 and (vals.get("HGB") or 99) < (_get_norms("HGB", age, sex) or {}).get("low", 99)
    cr_high = sev("CREATININE") > 0.25 and (vals.get("CREATININE") or 0) > (_get_norms("CREATININE", age, sex) or {}).get("high", 0)

    wbc_high = (vals.get("WBC") or 0) > (_get_norms("WBC", age, sex) or {}).get("high", 99)
    plt_low  = (vals.get("PLT") or 999) < (_get_norms("PLT", age, sex) or {}).get("low", 0)
    alt_high = (vals.get("ALT") or 0) > (_get_norms("ALT", age, sex) or {}).get("high", 99)
    hgb_low2 = hgb_low

    combos = [
        ("HGB_low_CREATININE_high", hgb_low and cr_high),
        ("WBC_high_PLT_low",        wbc_high and plt_low),
        ("HGB_low_PLT_low",         hgb_low2 and plt_low),
        ("WBC_high_ALT_high",       wbc_high and alt_high),
    ]
    for key, triggered in combos:
        if triggered and key in _COMORBIDITIES:
            c = _COMORBIDITIES[key]
            notes.append(f"[{c['urgency']}] {c['label']}: {c['note']}")

    return notes


def _red_flags(vals: dict, age: int, sex: str) -> List[str]:
    flags = []
    checks = [
        ("HGB",        "critical_low",  lambda v, t: v < t, lambda v: f"Haemoglobin critically low ({v} g/dL) — transfusion threshold"),
        ("PLT",        "critical_low",  lambda v, t: v < t, lambda v: f"Platelets critically low ({v} ×10³/µL) — spontaneous bleeding risk"),
        ("WBC",        "critical_high", lambda v, t: v > t, lambda v: f"WBC critically elevated ({v} ×10³/µL) — haematological emergency"),
        ("WBC",        "critical_low",  lambda v, t: v < t, lambda v: f"WBC critically low ({v} ×10³/µL) — severe infection risk"),
        ("CREATININE", "critical_high", lambda v, t: v > t, lambda v: f"Creatinine critically high ({v} mg/dL) — possible end-stage renal failure"),
        ("ALT",        "critical_high", lambda v, t: v > t, lambda v: f"ALT critically elevated ({v} U/L) — possible acute liver injury"),
    ]
    for param, thr_key, cmp, msg in checks:
        v = vals.get(param)
        thr = (_CRITICAL.get(param) or {}).get(thr_key)
        if v is not None and thr is not None and cmp(v, thr):
            flags.append(msg(v))
    return flags


# ---------------------------------------------------------------------------
# Follow-up questions per specialty
# ---------------------------------------------------------------------------

_FOLLOW_UPS = {
    "Hematology": [
        "Have you been unusually tired, short of breath, or pale recently?",
        "Any unexplained bruising, bleeding gums, or skin petechiae?",
        "Any night sweats, fever, or unexpected weight loss?",
    ],
    "Nephrology": [
        "Have you noticed changes in urine frequency, volume, or colour?",
        "Any swelling in your legs, ankles, or around the eyes?",
        "Do you have a history of diabetes, hypertension, or recurrent kidney infections?",
    ],
    "Hepatology": [
        "Any yellowing of the skin or whites of the eyes?",
        "Pain or pressure on the right side under the ribs?",
        "Any new medication, supplement, or alcohol use recently?",
    ],
    "Cardiology": [
        "Any chest pain, pressure, or tightness — at rest or during activity?",
        "Do you get short of breath with mild activity or when lying flat?",
        "Any swelling in your legs or feet?",
    ],
    "Gastroenterology": [
        "Any persistent abdominal pain or bloating?",
        "Changes in bowel habits — constipation or loose stools?",
        "Any blood in your stool or very dark/tarry stools?",
    ],
    "Pulmonology": [
        "Any persistent cough or wheezing?",
        "Do you feel short of breath at rest or with minimal exertion?",
        "Any history of smoking or occupational dust/fume exposure?",
    ],
    "ER": [
        "Are you currently experiencing chest pain or severe difficulty breathing?",
        "Any confusion, loss of consciousness, or sudden weakness?",
        "Have you had a recent fever above 39 °C or feel very unwell right now?",
    ],
    "POZ": [
        "When did you last have a routine check-up with your GP?",
        "Are you currently taking any prescription medications?",
        "Any new symptoms since your last blood draw?",
    ],
}


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------

def _patient_summary(
    top: str, patient_findings: List[str], comorbidities: List[str], age: int, sex: str
) -> str:
    sex_label = "female" if _sex_key(sex) == "f" else "male"

    if top == "ER":
        intro = (
            "⚠️ Your results contain critically abnormal values that may require urgent medical attention. "
            "Please go to the nearest Emergency Department or call emergency services immediately "
            "if you feel unwell, have chest pain, or difficulty breathing."
        )
    elif not patient_findings:
        intro = (
            "Your blood results look broadly normal for your age and sex. "
            "We recommend sharing them with your GP during a routine visit to confirm everything is in order."
        )
    else:
        specialty_lines = {
            "Hematology": "A blood specialist (haematologist) can help find the cause and suggest treatment.",
            "Nephrology": "A kidney specialist (nephrologist) can run further tests to protect your kidney function.",
            "Hepatology": "A liver specialist (hepatologist) can investigate and recommend next steps.",
            "Cardiology": "A heart specialist (cardiologist) can assess whether follow-up is needed.",
            "Gastroenterology": "A gut specialist (gastroenterologist) can investigate further.",
            "Pulmonology": "A lung specialist (pulmonologist) can assess your breathing.",
        }
        specialty_note = specialty_lines.get(top, "Your GP can help coordinate further tests.")
        findings_text = "; ".join(patient_findings[:3])
        intro = (
            f"Based on your blood results ({sex_label}, {age} years), we found: {findings_text}. "
            f"{specialty_note}"
        )

    if comorbidities:
        intro += f" Additionally, the pattern of results suggests: {comorbidities[0].split(': ', 1)[-1]}"

    return intro


def _clinical_summary(
    top: str,
    vals: dict,
    triage: Optional[TriageResultIn],
    clinical_findings: List[str],
    comorbidities: List[str],
    age: int,
    sex: str,
) -> str:
    flagged = _flagged_classes(triage)
    flagged_str = ", ".join(flagged) if flagged else "none above threshold"

    if triage and triage.predictions:
        top5 = sorted(triage.predictions, key=lambda p: p.probability, reverse=True)[:5]
        probs_str = ", ".join(f"{p.class_} {p.probability:.2f}" for p in top5)
    else:
        probs_str = "unavailable"

    abnormals_str = "; ".join(clinical_findings) if clinical_findings else "no significant abnormalities"

    # CKD staging
    cr = vals.get("CREATININE")
    ckd_note = ""
    if cr is not None:
        stage = _ckd_stage(cr, sex)
        if stage:
            ckd_note = f" CKD staging: {stage}."

    # Comorbidity note
    comorbidity_str = "; ".join(c.split(": ", 1)[-1] for c in comorbidities) if comorbidities else "none detected"

    urgency = "CRITICAL" if top == "ER" else ("HIGH" if len(flagged) > 1 else "ROUTINE")

    return (
        f"Patient: {age}yo {sex} | Urgency: {urgency}\n"
        f"BERT triage — flagged: {flagged_str}\n"
        f"Top probabilities: {probs_str}\n"
        f"Abnormal findings: {abnormals_str}.{ckd_note}\n"
        f"Comorbidity pattern: {comorbidity_str}\n"
        f"Primary referral: {top} | Mock explanation — real Opus 4.7 integration pending."
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/explain", response_model=ExplainResponse)
async def explain_mock(request: ExplainRequest) -> ExplainResponse:
    """
    MOCK /explain — medically-contextualised explanations for both patient and clinical modes.
    Replace with real Opus 4.7 call (api/explain.py) once API key is configured.
    """
    inp = request.input
    vals = {k: v for k, v in (inp.values or {}).items() if v is not None}
    top = _top_class(request.triage)

    patient_findings, clinical_findings = _analyse_abnormals(vals, inp.age, inp.sex)
    comorbidities = _detect_comorbidities(vals, inp.age, inp.sex)
    red_flags = _red_flags(vals, inp.age, inp.sex)

    patient_summary = _patient_summary(top, patient_findings, comorbidities, inp.age, inp.sex)
    clinical = _clinical_summary(
        top, vals, request.triage, clinical_findings, comorbidities, inp.age, inp.sex
    )

    flagged = _flagged_classes(request.triage)
    # Use follow-up questions for the top flagged specialty
    follow_up_key = flagged[0] if flagged else "POZ"
    follow_ups = _FOLLOW_UPS.get(follow_up_key, _FOLLOW_UPS["POZ"])

    return ExplainResponse(
        patientSummary=patient_summary,
        clinicalSummary=clinical if request.mode == "clinical" else None,
        followUpQuestions=follow_ups,
        redFlags=red_flags if red_flags else None,
    )
