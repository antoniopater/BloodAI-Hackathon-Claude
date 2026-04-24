from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
from pathlib import Path

router = APIRouter(tags=["predict"])

_cfg = Path(__file__).parent.parent / "config"
_LAB_NORMS: dict = json.loads((_cfg / "lab_norms.json").read_text())
_MED_CTX: dict = json.loads((_cfg / "medical_context.json").read_text())
_CRITICAL = _MED_CTX["critical_thresholds"]
_COMORBIDITIES = _MED_CTX["comorbidity_patterns"]


# ---------------------------------------------------------------------------
# Request / Response models  (keep shape expected by frontend types/api.ts)
# ---------------------------------------------------------------------------

class PatientInput(BaseModel):
    age: int
    sex: str  # "male" / "female"
    values: Dict[str, Optional[float]] = {}
    notes: Optional[str] = None
    collectedAt: Optional[str] = None


class PredictRequest(BaseModel):
    input: PatientInput


class AttentionWeight(BaseModel):
    param: str
    weight: float


class PredictResponse(BaseModel):
    predictions: List[Dict]
    attention: List[AttentionWeight]
    ece: Optional[float] = None
    modelVersion: Optional[str] = "mock-v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _age_group(age: int) -> str:
    if age < 18:
        return "kids"
    if age < 30:
        return "under_30"
    if age < 60:
        return "under_60"
    return "seniors"


def _sex_key(sex: str) -> str:
    return "m" if sex.lower() in ("m", "male") else "f"


def _get_norms(param: str, age: int, sex: str) -> Optional[dict]:
    return _LAB_NORMS.get(param, {}).get(_age_group(age), {}).get(_sex_key(sex))


def _severity(value: float, low: float, high: float) -> float:
    """0..1 — how far outside normal range. 0 = within range."""
    if value < low:
        return min(0.99, (low - value) / low * 1.5)
    if value > high:
        return min(0.99, (value - high) / high * 1.5)
    return 0.0


def _param_severity(param: str, value: Optional[float], age: int, sex: str) -> float:
    if value is None:
        return 0.0
    n = _get_norms(param, age, sex)
    if not n:
        return 0.0
    return _severity(value, n["low"], n["high"])


def _is_critical(param: str, value: Optional[float], direction: str) -> bool:
    if value is None or param not in _CRITICAL:
        return False
    c = _CRITICAL[param]
    if direction == "low":
        thr = c.get("critical_low")
        return thr is not None and value < thr
    thr = c.get("critical_high")
    return thr is not None and value > thr


# ---------------------------------------------------------------------------
# Core probability engine
# ---------------------------------------------------------------------------

def _compute_probs(vals: dict, age: int, sex: str) -> dict:
    def sev(p): return _param_severity(p, vals.get(p), age, sex)

    hgb_sev  = sev("HGB")
    cr_sev   = sev("CREATININE")
    alt_sev  = sev("ALT")
    ast_sev  = sev("AST")
    wbc_sev  = sev("WBC")
    plt_sev  = sev("PLT")
    urea_sev = sev("UREA")

    # Comorbidity bonuses
    ckd_anaemia = 0.15 if hgb_sev > 0.3 and cr_sev > 0.3 else 0.0
    leuk_hepato = 0.12 if wbc_sev > 0.3 and alt_sev > 0.3 else 0.0

    hemato = min(0.95, hgb_sev * 0.80 + wbc_sev * 0.55 + plt_sev * 0.45 + ckd_anaemia)
    nefro  = min(0.95, cr_sev  * 0.90 + urea_sev * 0.40 + ckd_anaemia * 0.5)
    hepato = min(0.95, alt_sev * 0.80 + ast_sev  * 0.35 + leuk_hepato)
    cardio = min(0.95, hgb_sev * 0.30)

    # ER: absolute-critical triggers
    wbc_v = vals.get("WBC")
    plt_v = vals.get("PLT")
    sor = 0.03
    if _is_critical("WBC", wbc_v, "high"):
        sor = 0.50
    elif _is_critical("PLT", plt_v, "low"):
        sor = 0.45
    elif _is_critical("HGB", vals.get("HGB"), "low"):
        sor = 0.40
    elif _is_critical("CREATININE", vals.get("CREATININE"), "high"):
        sor = 0.30
    elif _is_critical("ALT", vals.get("ALT"), "high"):
        sor = 0.25

    overall = max(hemato, nefro, hepato, cardio, sor)
    poz = max(0.05, 0.85 - overall)

    return {
        "POZ":              round(poz, 3),
        "Gastroenterology": round(max(0.06, 0.14 - overall * 0.08), 3),
        "Hematology":       round(max(0.05, hemato), 3),
        "Nephrology":       round(max(0.05, nefro), 3),
        "ER":               round(sor, 3),
        "Cardiology":       round(max(0.05, cardio), 3),
        "Pulmonology":      round(max(0.06, 0.10 - overall * 0.05), 3),
        "Hepatology":       round(max(0.05, hepato), 3),
    }


def _compute_attention(vals: dict, age: int, sex: str) -> List[AttentionWeight]:
    out = []
    for param in ["HGB", "CREATININE", "PLT", "WBC", "ALT", "AST", "MCV", "UREA"]:
        v = vals.get(param)
        if v is None:
            out.append(AttentionWeight(param=param, weight=0.01))
            continue
        n = _get_norms(param, age, sex)
        if not n:
            out.append(AttentionWeight(param=param, weight=0.02))
            continue
        sev = _severity(v, n["low"], n["high"])
        out.append(AttentionWeight(param=param, weight=round(0.02 + sev * 0.45, 3)))
    return out


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=PredictResponse)
async def predict_mock(request: PredictRequest) -> PredictResponse:
    """
    MOCK /predict — medically-contextualised triage probabilities.
    Uses age/sex-stratified reference ranges from lab_norms.json.
    Replace with real BERT inference once fine-tuning completes.
    """
    inp = request.input
    vals = {k: v for k, v in (inp.values or {}).items() if v is not None}

    probs = _compute_probs(vals, inp.age, inp.sex)
    predictions = [{"class": cls, "probability": prob} for cls, prob in probs.items()]
    attention = _compute_attention(vals, inp.age, inp.sex)

    return PredictResponse(
        predictions=predictions,
        attention=attention,
        ece=0.011,
        modelVersion="mock-v1",
    )
