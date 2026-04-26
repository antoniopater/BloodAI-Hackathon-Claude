"""
Medical-grade trend analysis for patient lab history.

Computes:
- Linear regression per parameter (slope per month, R²)
- Velocity alerts (rate-of-change exceeds clinical threshold)
- Threshold-crossing alerts (newly out-of-range)
- Comorbidity pattern alerts (cross-parameter signatures: CKD progression,
  bone-marrow suppression, iron deficiency, B12, hepatocellular, dehydration)
- Opus 4.7 narrative interpretation

History is provided by the client (frontend persists in localStorage); no DB.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trends", tags=["trends"])
# also expose as POST /trends (no prefix) so existing frontend client keeps working
root_router = APIRouter(tags=["trends"])

# ---------------------------------------------------------------------------
# Lab norms (age/sex-aware)
# ---------------------------------------------------------------------------

_cfg = Path(__file__).parent.parent / "config"
_LAB_NORMS: dict = json.loads((_cfg / "lab_norms.json").read_text())


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


# ---------------------------------------------------------------------------
# Clinical velocity thresholds
#   (max_per_month, unit, falling_is_bad)
#   Magnitude of change-per-month above which the trend is clinically alarming.
# ---------------------------------------------------------------------------

VELOCITY_THRESHOLDS: Dict[str, Tuple[float, str, bool]] = {
    "HGB":        (1.0,  "g/dL",     True),   # >1 g/dL/mo drop = workup
    "CREATININE": (0.3,  "mg/dL",    False),  # >0.3 mg/dL/mo rise = CKD progression
    "PLT":        (20.0, "K/uL",     True),   # >20k/mo drop = investigate
    "WBC":        (2.0,  "K/uL",     False),  # >2k/mo change either way
    "ALT":        (15.0, "U/L",      False),  # >15 U/L/mo rise = liver damage
    "AST":        (15.0, "U/L",      False),  # >15 U/L/mo rise = liver/muscle
    "MCV":        (3.0,  "fL",       False),  # >3 fL/mo change = investigate
    "UREA":       (5.0,  "mg/dL",    False),  # >5 mg/dL/mo rise = renal decline
    "HCT":        (2.0,  "%",        True),   # >2%/mo drop = bleeding
}

# Parameters where falling is the dangerous direction (anaemia, thrombocytopenia, leucopenia)
_FALLING_IS_BAD = {"HGB", "PLT", "HCT"}


# ---------------------------------------------------------------------------
# Comorbidity signatures (cross-parameter patterns)
#   "rising"/"falling" describes the value direction, not "good/bad".
# ---------------------------------------------------------------------------

COMORBIDITY_PATTERNS: List[dict] = [
    {
        "name": "CKD Progression",
        "params": {"CREATININE": "rising", "HGB": "falling"},
        "significance": "Progressive chronic kidney disease with secondary anemia.",
        "action": "URGENT: Nephrology referral. Add: eGFR, ACR, electrolytes, renal ultrasound.",
        "severity": "urgent",
    },
    {
        "name": "Hepatocellular Injury",
        "params": {"ALT": "rising", "AST": "rising"},
        "significance": "Active hepatocyte damage.",
        "action": "Liver panel, abdominal ultrasound, viral serology (HBV/HCV).",
        "severity": "warning",
    },
    {
        "name": "Bone Marrow Suppression",
        "params": {"HGB": "falling", "PLT": "falling", "WBC": "falling"},
        "significance": "Pancytopenia — possible bone-marrow injury.",
        "action": "URGENT: Hematology consultation. Consider bone-marrow biopsy.",
        "severity": "critical",
    },
    {
        "name": "Iron Deficiency Progression",
        "params": {"HGB": "falling", "MCV": "falling"},
        "significance": "Microcytic anemia — iron loss.",
        "action": "Ferritin, iron, TIBC. Rule out gastrointestinal bleeding.",
        "severity": "warning",
    },
    {
        "name": "B12/Folate Deficiency",
        "params": {"HGB": "falling", "MCV": "rising"},
        "significance": "Megaloblastic anemia.",
        "action": "Vitamin B12, folate. Neurological assessment.",
        "severity": "warning",
    },
    {
        "name": "Dehydration / Prerenal Azotemia",
        "params": {"CREATININE": "rising", "UREA": "rising", "HCT": "rising"},
        "significance": "Dehydration (prerenal azotemia).",
        "action": "Rehydrate, identify cause (vomiting, diarrhea, diuretics).",
        "severity": "warning",
    },
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class HistoryEntryIn(BaseModel):
    """Single lab session in the patient's history."""
    model_config = ConfigDict(populate_by_name=True)
    date: Optional[str] = Field(default=None, alias="collectedAt")  # ISO date or datetime
    age: int = 45
    sex: str = "female"
    values: Dict[str, Optional[float]] = {}


class TrendsRequest(BaseModel):
    history: List[HistoryEntryIn]


class TrendPoint(BaseModel):
    date: str
    value: float
    status: str  # 'low' | 'normal' | 'high'


class ParameterTrend(BaseModel):
    parameter: str
    unit: str
    direction: str  # 'improving' | 'stable' | 'worsening' | 'critical_worsening'

    slope: float
    r_squared: float
    delta_last_two: float
    delta_pct_last_two: float
    avg_monthly_change: float

    current_value: float
    previous_value: Optional[float] = None
    min_value: float
    max_value: float
    measurement_count: int
    days_span: int

    is_accelerating: bool = False
    crossed_threshold: bool = False

    normal_low: Optional[float] = None
    normal_high: Optional[float] = None

    points: List[TrendPoint] = []


class ClinicalAlert(BaseModel):
    severity: str  # 'info' | 'warning' | 'urgent' | 'critical'
    alert_type: str  # 'velocity' | 'threshold' | 'pattern' | 'acceleration'
    parameter: str
    title: str
    description: str
    clinical_significance: str
    recommended_action: str


class TrendDeltaOut(BaseModel):
    """Backwards-compatible 2-point delta (matches existing frontend TrendDelta)."""
    param: str
    previous: Optional[float] = None
    current: Optional[float] = None
    changePct: Optional[float] = None
    direction: str  # 'up' | 'down' | 'flat'


class TrendsResponse(BaseModel):
    deltas: List[TrendDeltaOut]
    interpretation: str
    urgency: str  # 'low' | 'medium' | 'high'
    trends: List[ParameterTrend] = []
    alerts: List[ClinicalAlert] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(s: Optional[str], fallback_index: int) -> date:
    """Parse ISO date/datetime; if missing, synthesize one a month apart."""
    if not s:
        # Synthesize: oldest = today - N months
        from datetime import timedelta
        return date.today() - timedelta(days=30 * (10 - fallback_index))
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        from datetime import timedelta
        return date.today() - timedelta(days=30 * (10 - fallback_index))


def _value_status(v: float, low: Optional[float], high: Optional[float]) -> str:
    if low is None or high is None:
        return "normal"
    if v < low:
        return "low"
    if v > high:
        return "high"
    return "normal"


def _compute_param_trend(
    param: str,
    series: List[Tuple[date, float]],
    age: int,
    sex: str,
) -> Optional[ParameterTrend]:
    """Compute trend statistics for a single parameter time-series."""
    if len(series) < 2:
        return None

    series = sorted(series, key=lambda t: t[0])
    dates = [d for d, _ in series]
    values = [v for _, v in series]

    days = np.array([(d - dates[0]).days for d in dates], dtype=float)
    y = np.array(values, dtype=float)

    # Linear regression
    if len(days) >= 2 and not np.allclose(days, days[0]):
        coeffs = np.polyfit(days, y, 1)
        slope_per_day = float(coeffs[0])
        slope_per_month = slope_per_day * 30.44
        y_pred = np.polyval(coeffs, days)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    else:
        slope_per_month = 0.0
        r_squared = 0.0

    delta_last = values[-1] - values[-2]
    delta_pct = (delta_last / values[-2] * 100.0) if values[-2] != 0 else 0.0

    # Acceleration: is the most recent rate of change faster than the prior one?
    is_accelerating = False
    if len(values) >= 3:
        d1 = max((dates[-1] - dates[-2]).days, 1)
        d0 = max((dates[-2] - dates[-3]).days, 1)
        recent_rate = abs(values[-1] - values[-2]) / d1
        older_rate = abs(values[-2] - values[-3]) / d0
        if older_rate > 0 and recent_rate > older_rate * 1.5:
            is_accelerating = True

    norms = _get_norms(param, age, sex) or {}
    low, high, unit = norms.get("low"), norms.get("high"), norms.get("unit", "")

    # Threshold crossing: previous in range, current out of range
    crossed = False
    if low is not None and high is not None:
        prev_in = low <= values[-2] <= high
        curr_out = (values[-1] < low) or (values[-1] > high)
        crossed = prev_in and curr_out

    direction = _classify_direction(param, slope_per_month, r_squared, max(0.0, r_squared))

    points = [
        TrendPoint(
            date=d.isoformat(),
            value=float(v),
            status=_value_status(float(v), low, high),
        )
        for d, v in zip(dates, values)
    ]

    return ParameterTrend(
        parameter=param,
        unit=unit,
        direction=direction,
        slope=round(slope_per_month, 4),
        r_squared=round(max(0.0, r_squared), 4),
        delta_last_two=round(delta_last, 3),
        delta_pct_last_two=round(delta_pct, 1),
        avg_monthly_change=round(slope_per_month, 3),
        current_value=float(values[-1]),
        previous_value=float(values[-2]),
        min_value=float(min(values)),
        max_value=float(max(values)),
        measurement_count=len(values),
        days_span=int((dates[-1] - dates[0]).days),
        is_accelerating=is_accelerating,
        crossed_threshold=crossed,
        normal_low=low,
        normal_high=high,
        points=points,
    )


def _classify_direction(param: str, slope: float, r_squared: float, _conf: float) -> str:
    """Translate slope into clinical direction. 'improving' = moving toward normal."""
    threshold = VELOCITY_THRESHOLDS.get(param, (0.1, "", False))
    max_safe = threshold[0]

    if abs(slope) < max_safe * 0.2:
        return "stable"

    falling_is_bad = param in _FALLING_IS_BAD

    if falling_is_bad:
        if slope < -max_safe:
            return "critical_worsening" if r_squared > 0.7 else "worsening"
        if slope < 0:
            return "worsening"
        return "improving"
    else:
        if slope > max_safe:
            return "critical_worsening" if r_squared > 0.7 else "worsening"
        if slope > 0:
            return "worsening"
        return "improving"


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


def _generate_alerts(trends: List[ParameterTrend]) -> List[ClinicalAlert]:
    alerts: List[ClinicalAlert] = []
    trend_map = {t.parameter: t for t in trends}

    # 1. Velocity alerts
    for t in trends:
        if t.parameter not in VELOCITY_THRESHOLDS:
            continue
        max_safe, unit, _ = VELOCITY_THRESHOLDS[t.parameter]
        if abs(t.slope) > max_safe:
            severity = "critical" if abs(t.slope) > max_safe * 2 else "urgent"
            direction_word = "drop" if t.slope < 0 else "rise"
            alerts.append(ClinicalAlert(
                severity=severity,
                alert_type="velocity",
                parameter=t.parameter,
                title=f"Rapid {t.parameter} {direction_word}",
                description=(
                    f"{t.parameter} is changing by {abs(t.slope):.2f} {unit}/month "
                    f"(safety threshold: {max_safe} {unit}/month). "
                    f"Trend based on {t.measurement_count} measurements over {t.days_span} days."
                ),
                clinical_significance=(
                    f"Rate of change exceeds the safe threshold by "
                    f"{max_safe * (2 if severity == 'critical' else 1):.1f}×. "
                    f"R²={t.r_squared:.2f} "
                    f"{'(strong trend)' if t.r_squared > 0.7 else '(moderate trend)'}."
                ),
                recommended_action=(
                    f"Repeat {t.parameter} within "
                    f"{'24 hours' if severity == 'critical' else '1–2 weeks'}. "
                    f"{'Consider an urgent consultation.' if severity == 'critical' else 'Monitor the trend.'}"
                ),
            ))

        # 2. Acceleration alert
        if t.is_accelerating and t.direction in ("worsening", "critical_worsening"):
            alerts.append(ClinicalAlert(
                severity="warning",
                alert_type="acceleration",
                parameter=t.parameter,
                title=f"{t.parameter} — trend ACCELERATING",
                description=(
                    f"The rate of change in {t.parameter} is rising. "
                    f"The most recent change ({t.delta_last_two:+.2f}) is faster than the previous one."
                ),
                clinical_significance="An accelerating trend may indicate clinical deterioration.",
                recommended_action="Shorten the interval between tests. Consider a specialist consultation.",
            ))

        # 3. Threshold-crossing alert
        if t.crossed_threshold:
            alerts.append(ClinicalAlert(
                severity="warning",
                alert_type="threshold",
                parameter=t.parameter,
                title=f"{t.parameter} crossed the reference range",
                description=(
                    f"The {t.parameter} value ({t.current_value}) "
                    f"moved outside the reference range in the most recent measurement."
                ),
                clinical_significance="A new deviation from the reference range warrants clinical review.",
                recommended_action="Repeat the test in 2–4 weeks. If the deviation persists, seek a consultation.",
            ))

    # 4. Comorbidity pattern alerts
    for pattern in COMORBIDITY_PATTERNS:
        params = pattern["params"]
        if not all(p in trend_map for p in params):
            continue

        match = True
        for p, expected_dir in params.items():
            t = trend_map[p]
            actual_slope = t.slope
            # Direction must be non-trivial
            if abs(actual_slope) < VELOCITY_THRESHOLDS.get(p, (0.05, "", False))[0] * 0.2:
                match = False
                break
            if expected_dir == "rising" and actual_slope <= 0:
                match = False
                break
            if expected_dir == "falling" and actual_slope >= 0:
                match = False
                break

        if match:
            alerts.append(ClinicalAlert(
                severity=pattern["severity"],
                alert_type="pattern",
                parameter=",".join(params.keys()),
                title=pattern["name"],
                description=(
                    "Pattern detected: "
                    + ", ".join(f"{p} {d}" for p, d in params.items())
                ),
                clinical_significance=pattern["significance"],
                recommended_action=pattern["action"],
            ))

    severity_order = {"critical": 0, "urgent": 1, "warning": 2, "info": 3}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 99))
    return alerts


# ---------------------------------------------------------------------------
# Opus narrative
# ---------------------------------------------------------------------------

_MODEL_ID = os.getenv("BLOODAI_MODEL_ID", "claude-opus-4-7")
_USE_OPUS_API = os.getenv("USE_OPUS_API", "true").lower() in ("true", "1", "yes")
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import Anthropic
        except ImportError:
            return None
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        _client = Anthropic(api_key=api_key)
    return _client


def _opus_narrative(
    trends: List[ParameterTrend],
    alerts: List[ClinicalAlert],
    age: int,
    sex: str,
) -> str:
    """Ask Opus 4.7 to write a contextual narrative interpretation."""
    if not _USE_OPUS_API:
        return _fallback_narrative(trends, alerts)
    client = _get_client()
    if client is None:
        return _fallback_narrative(trends, alerts)

    trends_text = "\n".join([
        f"- {t.parameter}: {t.points[0].value if t.points else '?'} → {t.current_value} {t.unit} "
        f"(direction={t.direction}, slope={t.slope:+.3f}/month, R²={t.r_squared:.2f}, "
        f"{t.measurement_count} measurements / {t.days_span} days)"
        for t in trends
    ]) or "(insufficient data)"

    alerts_text = "\n".join([
        f"- [{a.severity.upper()}] {a.title} — {a.clinical_significance}"
        for a in alerts[:6]
    ]) or "(no alerts)"

    sex_label = "female" if _sex_key(sex) == "f" else "male"
    prompt = f"""Patient: {age} years old, {sex_label}.

Parameter trends (chronological):
{trends_text}

Clinical alerts:
{alerts_text}

Write a SIMPLE explanation for the patient (max 200 words, no medical jargon):
1. Which values are improving and which are worsening — and what that means in practice.
2. Is there a concerning pattern (e.g. kidney disease, anemia, liver problems)?
3. What should the patient do first, and how urgent is it.

Style: empathetic, concrete, direct ("Your hemoglobin..."). No bullet points — write in paragraphs.
End with this exact sentence: "Please consult these results with a doctor before making any health decisions."
Do not diagnose — use phrases like "may indicate", "worth checking".
Respond in English.
"""

    try:
        msg = client.messages.create(
            model=_MODEL_ID,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:
        logger.warning(f"Opus narrative failed: {exc} — using fallback")
        return _fallback_narrative(trends, alerts)


def _fallback_narrative(trends: List[ParameterTrend], alerts: List[ClinicalAlert]) -> str:
    if not trends:
        return "Not enough data for a trend analysis — at least two measurements are required."
    parts = []
    worsening = [t for t in trends if t.direction in ("worsening", "critical_worsening")]
    improving = [t for t in trends if t.direction == "improving"]
    if worsening:
        parts.append("Worsening: " + ", ".join(
            f"{t.parameter} ({t.points[0].value}→{t.current_value} {t.unit})"
            for t in worsening
        ) + ".")
    if improving:
        parts.append("Improving: " + ", ".join(
            f"{t.parameter} ({t.points[0].value}→{t.current_value} {t.unit})"
            for t in improving
        ) + ".")
    if alerts:
        critical = [a for a in alerts if a.severity in ("critical", "urgent")]
        if critical:
            parts.append("Urgent signals detected: " + "; ".join(a.title for a in critical[:3]) + ".")
    parts.append("Please consult these results with a doctor before making any health decisions.")
    return " ".join(parts)


def _overall_urgency(alerts: List[ClinicalAlert]) -> str:
    if any(a.severity == "critical" for a in alerts):
        return "high"
    if any(a.severity == "urgent" for a in alerts):
        return "high"
    if any(a.severity == "warning" for a in alerts):
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


def _compute_response(req: TrendsRequest) -> TrendsResponse:
    if not req.history or len(req.history) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least two history entries are required for trend analysis.",
        )

    # Sort entries chronologically (using parsed dates)
    indexed = list(enumerate(req.history))
    parsed = [(i, _parse_date(e.date, i), e) for i, e in indexed]
    parsed.sort(key=lambda t: t[1])

    age = parsed[-1][2].age
    sex = parsed[-1][2].sex

    # Build per-parameter time-series
    series_by_param: Dict[str, List[Tuple[date, float]]] = {}
    for _, dt, entry in parsed:
        for param, val in (entry.values or {}).items():
            if val is None:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            series_by_param.setdefault(param.upper(), []).append((dt, v))

    trends: List[ParameterTrend] = []
    for param, series in series_by_param.items():
        if len(series) < 2:
            continue
        t = _compute_param_trend(param, series, age, sex)
        if t is not None:
            trends.append(t)

    # Order: critical first, then by parameter name
    direction_order = {"critical_worsening": 0, "worsening": 1, "improving": 2, "stable": 3}
    trends.sort(key=lambda t: (direction_order.get(t.direction, 9), t.parameter))

    alerts = _generate_alerts(trends)

    # Backwards-compatible 2-point deltas
    deltas: List[TrendDeltaOut] = []
    for t in trends:
        prev = t.previous_value
        curr = t.current_value
        pct = None
        if prev is not None and prev != 0:
            pct = (curr - prev) / prev * 100.0
        if pct is None or abs(pct) < 1:
            direction = "flat"
        elif pct > 0:
            direction = "up"
        else:
            direction = "down"
        deltas.append(TrendDeltaOut(
            param=t.parameter,
            previous=prev,
            current=curr,
            changePct=round(pct, 1) if pct is not None else None,
            direction=direction,
        ))

    interpretation = _opus_narrative(trends, alerts, age, sex)
    urgency = _overall_urgency(alerts)

    return TrendsResponse(
        deltas=deltas,
        interpretation=interpretation,
        urgency=urgency,
        trends=trends,
        alerts=alerts,
    )


@router.post("", response_model=TrendsResponse)
async def trends_with_prefix(req: TrendsRequest) -> TrendsResponse:
    """POST /trends/ — analyze patient lab history."""
    return _compute_response(req)


@root_router.post("/trends", response_model=TrendsResponse)
async def trends_root(req: TrendsRequest) -> TrendsResponse:
    """POST /trends — frontend-compatible alias."""
    return _compute_response(req)
