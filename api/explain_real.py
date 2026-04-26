"""
Real /explain endpoint — Opus 4.7 generates medically-contextualised explanations.

Swap-in replacement for api/explain_mock.py (same request/response schema).
Rule-based helpers (abnormality detection, red flags, follow-up questions) are
retained from the mock so structured medical data is still available.
Opus is called only for free-text summaries.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

router = APIRouter(tags=["explain"])

# ---------------------------------------------------------------------------
# Medical context
# ---------------------------------------------------------------------------

_cfg = Path(__file__).parent.parent / "config"
_LAB_NORMS: dict = json.loads((_cfg / "lab_norms.json").read_text())
_MED_CTX: dict = json.loads((_cfg / "medical_context.json").read_text())
_CRITICAL = _MED_CTX["critical_thresholds"]
_COMORBIDITIES = _MED_CTX["comorbidity_patterns"]
_CKD_STAGING = _MED_CTX["creatinine_ckd_staging"]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MODEL = os.getenv("BLOODAI_MODEL_ID", "claude-opus-4-7")
_USE_OPUS_API = os.getenv("USE_OPUS_API", "true").lower() in ("true", "1", "yes")
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import Anthropic
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="anthropic SDK not installed. Run: pip install -U anthropic",
            )
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY environment variable not set.",
            )
        _client = Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Request / Response models (identical to explain_mock.py)
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


class SuggestedTest(BaseModel):
    """An additional lab/imaging test the patient should consider getting."""
    name: str  # e.g. "Ferrytyna" / "Urinalysis" / "TSH"
    reason: str  # short justification (max ~120 chars)
    urgency: str = "routine"  # "routine" | "soon" | "urgent"


class ExplainResponse(BaseModel):
    patientSummary: str
    clinicalSummary: Optional[str] = None
    followUpQuestions: Optional[List[str]] = None
    redFlags: Optional[List[str]] = None
    suggestedTests: Optional[List[SuggestedTest]] = None


# ---------------------------------------------------------------------------
# Rule-based helpers (ported from explain_mock.py — unchanged)
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


def _analyse_abnormals(
    vals: Dict[str, Optional[float]], age: int, sex: str
) -> tuple[List[str], List[str]]:
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

    hgb_low  = sev("HGB") > 0.25 and (vals.get("HGB") or 99) < (_get_norms("HGB", age, sex) or {}).get("low", 99)
    cr_high  = sev("CREATININE") > 0.25 and (vals.get("CREATININE") or 0) > (_get_norms("CREATININE", age, sex) or {}).get("high", 0)
    wbc_high = (vals.get("WBC") or 0) > (_get_norms("WBC", age, sex) or {}).get("high", 99)
    plt_low  = (vals.get("PLT") or 999) < (_get_norms("PLT", age, sex) or {}).get("low", 0)
    alt_high = (vals.get("ALT") or 0) > (_get_norms("ALT", age, sex) or {}).get("high", 99)

    combos = [
        ("HGB_low_CREATININE_high", hgb_low and cr_high),
        ("WBC_high_PLT_low",        wbc_high and plt_low),
        ("HGB_low_PLT_low",         hgb_low and plt_low),
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

_SPECIALTY_DISPLAY = {
    "Hematology": "a blood specialist (haematologist)",
    "Nephrology": "a kidney specialist (nephrologist)",
    "Hepatology": "a liver specialist (hepatologist)",
    "Cardiology": "a heart specialist (cardiologist)",
    "Gastroenterology": "a gut specialist (gastroenterologist)",
    "Pulmonology": "a lung specialist (pulmonologist)",
    "ER": "the Emergency Department",
    "POZ": "your GP",
}


# ---------------------------------------------------------------------------
# Opus response parsers
# ---------------------------------------------------------------------------

def _parse_opus_json(raw: str) -> dict:
    """Extract a JSON object from Opus output. Tolerates leading/trailing text
    and ```json fences. Returns {} if parsing fails."""
    if not raw:
        return {}
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        logger.warning("Opus returned non-parseable JSON; using raw fallback")
        return {}


_VALID_URGENCY = {"routine", "soon", "urgent"}


def _parse_suggested_tests(raw) -> List[SuggestedTest]:
    """Coerce Opus' suggested_tests array into validated SuggestedTest models."""
    if not isinstance(raw, list):
        return []
    out: List[SuggestedTest] = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        reason = (item.get("reason") or "").strip()
        urgency = (item.get("urgency") or "routine").strip().lower()
        if not name:
            continue
        if urgency not in _VALID_URGENCY:
            urgency = "routine"
        out.append(SuggestedTest(name=name[:80], reason=reason[:200], urgency=urgency))
    return out


# ---------------------------------------------------------------------------
# Opus prompt builders
# ---------------------------------------------------------------------------

def _build_patient_prompt(inp: ExplainInput, vals: dict, top: str, findings: List[str], comorbidities: List[str]) -> str:
    sex_label = "female" if _sex_key(inp.sex) == "f" else "male"
    specialist = _SPECIALTY_DISPLAY.get(top, "your doctor")

    findings_block = ""
    if findings:
        findings_block = "\nAbnormal values found:\n" + "\n".join(f"- {f}" for f in findings[:5])

    comorbidity_block = ""
    if comorbidities:
        comorbidity_block = f"\nNote: {comorbidities[0].split(': ', 1)[-1]}"

    emergency_line = ""
    if top == "ER":
        emergency_line = "\nIMPORTANT: Values are critically abnormal — mention going to Emergency Department urgently."

    return f"""You are a medical assistant explaining blood test results to a patient. Return ONLY valid JSON, no other text.

Patient: {inp.age}-year-old {sex_label}
{findings_block}{comorbidity_block}{emergency_line}
AI model suggests referral to: {specialist}

Return this exact JSON structure:
{{
  "patient_summary": "2-3 plain-English sentences (max 120 words). Empathetic, non-technical. State which specialist might help and why. End with: 'Please consult your doctor before making any health decisions.' Do NOT use 'diagnose' or definitive claims. Do NOT repeat raw numbers unless critical.",
  "suggested_tests": [
    {{"name": "<Test name>", "reason": "<one short sentence — what it would clarify>", "urgency": "routine|soon|urgent"}}
  ]
}}

For "suggested_tests": list 3-5 concrete additional lab/imaging tests that would clarify the abnormal findings or rule out the suspected condition. Each "reason" must be plain-language (max ~120 chars). Use "urgent" only if the result is life-threatening (e.g. ER referral). Use English test names. Examples: "Ferritin", "Reticulocyte count", "B12", "Urinalysis", "eGFR", "Lipid panel", "TSH", "Hepatitis panel"."""


def _build_clinical_prompt(
    inp: ExplainInput, vals: dict, triage: Optional[TriageResultIn],
    clinical_findings: List[str], comorbidities: List[str]
) -> str:
    sex_label = "female" if _sex_key(inp.sex) == "f" else "male"
    top = _top_class(triage)
    flagged = _flagged_classes(triage)
    urgency = "CRITICAL" if "ER" in flagged else ("HIGH" if len(flagged) > 1 else "ROUTINE")

    vals_str = ", ".join(f"{k}: {v}" for k, v in vals.items())
    abnormals_str = "; ".join(clinical_findings) if clinical_findings else "none"
    comorbidity_str = "; ".join(c.split(": ", 1)[-1] for c in comorbidities) if comorbidities else "none"

    probs_str = ""
    if triage and triage.predictions:
        top5 = sorted(triage.predictions, key=lambda p: p.probability, reverse=True)[:5]
        probs_str = ", ".join(f"{p.class_} {p.probability:.2f}" for p in top5)

    cr = vals.get("CREATININE")
    ckd_note = ""
    if cr is not None:
        stage = _ckd_stage(cr, inp.sex)
        if stage:
            ckd_note = f"\nCKD staging (by creatinine): {stage}"

    return f"""Generate medical explanations for blood test results. Return ONLY valid JSON, no other text.

Patient: {inp.age}yo {sex_label}
Lab values: {vals_str}
Abnormal findings: {abnormals_str}
Comorbidity patterns: {comorbidity_str}{ckd_note}
BERT triage probabilities: {probs_str}
Flagged specialties: {', '.join(flagged)}
Urgency level: {urgency}
Primary referral: {top}

Return this exact JSON structure:
{{
  "patient_summary": "2-3 plain-English sentences for the patient (max 120 words, empathetic, end with 'consult your doctor')",
  "clinical_assessment": "Structured note: Urgency: {urgency}. Key findings: [list]. Primary referral: {top}. Recommended next steps: [list]. (max 100 words)",
  "suggested_tests": [
    {{"name": "<Test>", "reason": "<clinical justification, 1 sentence>", "urgency": "routine|soon|urgent"}}
  ]
}}

For "suggested_tests": list 3-6 concrete follow-up labs/imaging that confirm or rule out the differential. Use specific test names (Ferritin, TIBC, Reticulocytes, eGFR, Urinalysis, ANA, Hepatitis panel, AbdoUS, etc.). Match urgency to the case (urgent only if {urgency} is CRITICAL)."""


# ---------------------------------------------------------------------------
# Mock response generators (for testing, when USE_OPUS_API=false)
# ---------------------------------------------------------------------------

_MOCK_SUGGESTED_TESTS: Dict[str, List[Dict[str, str]]] = {
    "Hematology": [
        {"name": "Ferritin", "reason": "Distinguish iron-deficiency from other anemias.", "urgency": "soon"},
        {"name": "Reticulocyte count", "reason": "Assess bone-marrow response to anemia.", "urgency": "soon"},
        {"name": "Vitamin B12 + Folate", "reason": "Rule out megaloblastic causes.", "urgency": "routine"},
        {"name": "Peripheral blood smear", "reason": "Look for abnormal cell morphology.", "urgency": "routine"},
    ],
    "Nephrology": [
        {"name": "eGFR (CKD-EPI)", "reason": "Quantify kidney function.", "urgency": "soon"},
        {"name": "Urinalysis + ACR", "reason": "Detect proteinuria / haematuria.", "urgency": "soon"},
        {"name": "Electrolytes (Na, K)", "reason": "Check for renal-related imbalances.", "urgency": "soon"},
        {"name": "Renal ultrasound", "reason": "Rule out structural causes.", "urgency": "routine"},
    ],
    "Hepatology": [
        {"name": "GGT + Alkaline phosphatase", "reason": "Localise the liver injury (cholestatic vs hepatocellular).", "urgency": "soon"},
        {"name": "Hepatitis B/C panel", "reason": "Rule out viral hepatitis.", "urgency": "soon"},
        {"name": "Bilirubin (total + direct)", "reason": "Assess liver excretory function.", "urgency": "routine"},
        {"name": "Abdominal ultrasound", "reason": "Visualise liver parenchyma & bile ducts.", "urgency": "routine"},
    ],
    "Cardiology": [
        {"name": "Lipid panel", "reason": "Cardiovascular risk stratification.", "urgency": "routine"},
        {"name": "Troponin (high-sensitivity)", "reason": "Rule out myocardial injury.", "urgency": "soon"},
        {"name": "BNP / NT-proBNP", "reason": "Assess for heart failure.", "urgency": "soon"},
        {"name": "12-lead ECG", "reason": "Detect arrhythmia or ischaemia.", "urgency": "routine"},
    ],
    "Gastroenterology": [
        {"name": "Faecal occult blood / calprotectin", "reason": "Screen for GI bleeding or inflammation.", "urgency": "soon"},
        {"name": "Lipase + amylase", "reason": "Rule out pancreatitis.", "urgency": "routine"},
        {"name": "H. pylori test", "reason": "Common cause of gastric pathology.", "urgency": "routine"},
    ],
    "Pulmonology": [
        {"name": "Chest X-ray", "reason": "Visualise lung fields.", "urgency": "soon"},
        {"name": "Spirometry", "reason": "Quantify lung function.", "urgency": "routine"},
        {"name": "D-dimer", "reason": "Rule out pulmonary embolism if suspected.", "urgency": "soon"},
    ],
    "ER": [
        {"name": "Complete metabolic panel", "reason": "Full electrolyte / kidney / liver baseline.", "urgency": "urgent"},
        {"name": "Lactate", "reason": "Assess tissue perfusion / sepsis risk.", "urgency": "urgent"},
        {"name": "Coagulation panel (PT/INR/aPTT)", "reason": "Bleeding risk evaluation.", "urgency": "urgent"},
        {"name": "Type & screen", "reason": "Prepare for possible transfusion.", "urgency": "urgent"},
    ],
    "POZ": [
        {"name": "TSH", "reason": "Routine thyroid screening.", "urgency": "routine"},
        {"name": "Lipid panel", "reason": "Cardiovascular risk baseline.", "urgency": "routine"},
        {"name": "Vitamin D (25-OH)", "reason": "Common deficiency causing fatigue.", "urgency": "routine"},
        {"name": "HbA1c", "reason": "Diabetes screening.", "urgency": "routine"},
    ],
}


def _mock_suggested_tests(top_class: str) -> List[SuggestedTest]:
    return [SuggestedTest(**t) for t in _MOCK_SUGGESTED_TESTS.get(top_class, _MOCK_SUGGESTED_TESTS["POZ"])]


def _mock_explain_response(request: ExplainRequest) -> ExplainResponse:
    """Generate mock explain response without calling Opus."""
    inp = request.input
    vals = {k: v for k, v in (inp.values or {}).items() if v is not None}
    flagged = _flagged_classes(request.triage)
    follow_ups = _FOLLOW_UPS.get(flagged[0] if flagged else "POZ", _FOLLOW_UPS["POZ"])
    patient_findings, clinical_findings = _analyse_abnormals(vals, inp.age, inp.sex)
    top = _top_class(request.triage)
    suggested = _mock_suggested_tests(top)

    mode = request.mode
    if mode == "clinical":
        patient_summary = f"[MOCK] {len(patient_findings)} abnormal findings detected in {inp.age}yo {inp.sex}."
        clinical_summary = f"Urgency: ROUTINE. Key findings: {', '.join(clinical_findings[:3])}."
        return ExplainResponse(
            patientSummary=patient_summary,
            clinicalSummary=clinical_summary,
            followUpQuestions=follow_ups,
            redFlags=None,
            suggestedTests=suggested,
        )
    else:  # patient mode
        specialist = _SPECIALTY_DISPLAY.get(top, "your doctor")
        patient_summary = f"[MOCK] Your blood test suggests you should see {specialist}. Please consult your doctor before making any health decisions."
        return ExplainResponse(
            patientSummary=patient_summary,
            clinicalSummary=None,
            followUpQuestions=follow_ups,
            redFlags=None,
            suggestedTests=suggested,
        )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/explain", response_model=ExplainResponse)
async def explain_real(request: ExplainRequest) -> ExplainResponse:
    """Real /explain — Opus 4.7 generates contextualised summaries (or mock if USE_OPUS_API=false)."""
    inp = request.input
    vals = {k: v for k, v in (inp.values or {}).items() if v is not None}
    top = _top_class(request.triage)

    # Rule-based analysis (fast, no API call)
    patient_findings, clinical_findings = _analyse_abnormals(vals, inp.age, inp.sex)
    comorbidities = _detect_comorbidities(vals, inp.age, inp.sex)
    red_flags = _red_flags(vals, inp.age, inp.sex)

    flagged = _flagged_classes(request.triage)
    follow_ups = _FOLLOW_UPS.get(flagged[0] if flagged else "POZ", _FOLLOW_UPS["POZ"])

    if not _USE_OPUS_API:
        logger.info("USE_OPUS_API=false — returning mock explain response")
        return _mock_explain_response(request)

    # Call Opus
    client = _get_client()
    mode = request.mode

    try:
        if mode == "clinical":
            prompt = _build_clinical_prompt(inp, vals, request.triage, clinical_findings, comorbidities)
            resp = client.messages.create(
                model=_MODEL,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()

            data = _parse_opus_json(raw)
            patient_summary = data.get("patient_summary") or raw
            clinical_summary = data.get("clinical_assessment") or None
            suggested_tests = _parse_suggested_tests(data.get("suggested_tests"))

            return ExplainResponse(
                patientSummary=patient_summary,
                clinicalSummary=clinical_summary,
                followUpQuestions=follow_ups,
                redFlags=red_flags or None,
                suggestedTests=suggested_tests or None,
            )

        else:  # patient mode
            prompt = _build_patient_prompt(inp, vals, top, patient_findings, comorbidities)
            resp = client.messages.create(
                model=_MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()

            data = _parse_opus_json(raw)
            patient_summary = data.get("patient_summary") or raw
            suggested_tests = _parse_suggested_tests(data.get("suggested_tests"))

            return ExplainResponse(
                patientSummary=patient_summary,
                clinicalSummary=None,
                followUpQuestions=follow_ups,
                redFlags=red_flags or None,
                suggestedTests=suggested_tests or None,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Opus API error: {exc}")
        raise HTTPException(status_code=503, detail=f"Opus API error: {exc}")
