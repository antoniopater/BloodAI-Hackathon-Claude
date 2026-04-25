# Mock API — Medical Context (`/predict` + `/explain`)

## Purpose and context

The BERT model is fine-tuning in the background (estimated ~8 hours).
While it runs, the frontend needs working endpoints to test the full user flow.
These mock endpoints replace random/hardcoded probabilities with **medically coherent logic**:
age/sex-stratified reference ranges, deviation-based severity scoring, comorbidity detection,
and CKD staging — so the demo looks real, not random.

**Replacement timeline:**
1. When `checkpoints/finetune/` is ready → swap `predict_mock_router` for the real BERT inference block in `api/main.py` (lines 49–53, see section below).
2. When `ANTHROPIC_API_KEY` is set → replace `explain_mock_router` with `api/explain.py` (real Opus 4.7).

---

## Files changed in this session

| File | Status | Description |
|------|--------|-------------|
| `config/medical_context.json` | **NEW** | Clinical knowledge: critical thresholds, 5 comorbidity patterns, CKD staging |
| `api/predict_mock.py` | **Rewritten** | Age/sex-aware severity engine → realistic specialty probabilities |
| `api/explain_mock.py` | **Rewritten** | Contextual explanations (patient + clinical mode) using real norms |

`api/main.py` was **not changed** — it already imports and registers both routers.

---

## Medical logic architecture

### Reference ranges (`config/lab_norms.json`)

Norms are stratified by **age group** and **sex**:

| Age group key | Ages |
|---------------|------|
| `kids` | 0–17 |
| `under_30` | 18–29 |
| `under_60` | 30–59 |
| `seniors` | 60+ |

Sex key: `"m"` or `"f"` (mapped from frontend `"male"` / `"female"`).

Each norm entry: `{ "low": float, "high": float, "unit": string }`.

Helper functions in both mock files:
```python
_age_group(age: int) -> str          # maps age to group key
_sex_key(sex: str)   -> str          # "male"/"m" -> "m", else "f"
_get_norms(param, age, sex) -> dict  # looks up lab_norms.json
```

### Severity scoring

```
severity(value, low, high):
  if value < low:  return min(0.99, (low - value) / low  * 1.5)
  if value > high: return min(0.99, (value - high) / high * 1.5)
  else:            return 0.0
```

Example — HGB = 8.5 g/dL, senior male norm [12.5, 17.5]:
```
severity = (12.5 - 8.5) / 12.5 * 1.5 = 0.48
```

### Probability engine (`_compute_probs`)

| Parameter | Primary specialty | Weight | Secondary |
|-----------|------------------|--------|-----------|
| HGB (low) | Hematology | 0.80 | Cardiology 0.30 |
| CREATININE (high) | Nephrology | 0.90 | — |
| UREA (high) | Nephrology boost | 0.40 | — |
| ALT (high) | Hepatology | 0.80 | — |
| AST (high) | Hepatology boost | 0.35 | — |
| WBC (any dev.) | Hematology | 0.55 | ER if critical |
| PLT (low) | Hematology | 0.45 | ER if critical |

**POZ** = `max(0.05, 0.85 − overall_severity)` — rises only when all parameters are normal.

**Gastroenterology / Pulmonology** — low baseline (0.06–0.14), reduced by overall severity; no direct lab trigger in the current parameter set.

### Comorbidity bonuses

Detected when two parameters are simultaneously abnormal:

| Pattern key | Trigger | Bonus |
|-------------|---------|-------|
| `HGB_low_CREATININE_high` | HGB sev > 0.3 AND CR sev > 0.3 | +0.15 to both Nephrology and Hematology |
| `WBC_high_ALT_high` | WBC high AND ALT high | +0.12 to Hepatology |

Full pattern catalogue in `config/medical_context.json` → `comorbidity_patterns`.

### ER triggering logic

ER is triggered by **absolute critical thresholds** (from `medical_context.json → critical_thresholds`), not by relative severity:

| Condition | ER probability |
|-----------|---------------|
| WBC > 30 K/µL | 0.50 |
| PLT < 20 K/µL | 0.45 |
| HGB < 7 g/dL | 0.40 |
| CREATININE > 4 mg/dL | 0.30 |
| ALT > 500 U/L | 0.25 |
| No critical value | 0.03 |

---

## API contract

### `POST /predict`

**Request** (matches `types/api.ts → PredictRequest`):
```json
{
  "input": {
    "age": 65,
    "sex": "male",
    "values": {
      "HGB": 8.5,
      "CREATININE": 3.2,
      "PLT": 180,
      "WBC": 7.5,
      "ALT": 35
    }
  }
}
```

**Response** (matches `types/medical.ts → TriageResult`):
```json
{
  "predictions": [
    { "class": "Nephrology",  "probability": 0.95 },
    { "class": "Hematology",  "probability": 0.53 },
    { "class": "Cardiology",  "probability": 0.14 },
    { "class": "POZ",         "probability": 0.05 },
    ...
  ],
  "attention": [
    { "param": "CREATININE", "weight": 0.47 },
    { "param": "HGB",        "weight": 0.24 },
    ...
  ],
  "ece": 0.011,
  "modelVersion": "mock-v1"
}
```

### `POST /explain`

**Request** (matches `types/api.ts → ExplainRequest`):
```json
{
  "input": {
    "age": 65,
    "sex": "male",
    "values": { "HGB": 8.5, "CREATININE": 3.2 }
  },
  "triage": {
    "predictions": [
      { "class": "Nephrology", "probability": 0.95 },
      { "class": "Hematology", "probability": 0.53 }
    ],
    "attention": []
  },
  "mode": "patient"
}
```

**Response** (matches `types/medical.ts → OpusExplanation`):
```json
{
  "patientSummary": "Based on your blood results (male, 65 years), we found: Haemoglobin low (8.5 g/dL) — reference 12.5–17.5; Creatinine high (3.2 mg/dL) — reference 0.74–1.35. A kidney specialist (nephrologist) can run further tests... Additionally, the pattern suggests: Low HGB + elevated creatinine — classic CKD-anaemia.",
  "clinicalSummary": null,
  "followUpQuestions": [
    "Have you noticed changes in urine frequency, volume, or colour?",
    "Any swelling in your legs, ankles, or around the eyes?",
    "Do you have a history of diabetes, hypertension, or recurrent kidney infections?"
  ],
  "redFlags": null
}
```

When `mode = "clinical"`, `clinicalSummary` is populated with:
- flagged specialties + top-5 probabilities
- abnormal findings with exact values and reference ranges
- CKD staging (e.g. "CKD G3b — moderate–severe")
- comorbidity assessment
- urgency level (ROUTINE / HIGH / CRITICAL)

---

## Usage examples

### Case 1: 65-year-old male, CKD + anaemia

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "age": 65, "sex": "male",
      "values": {"HGB": 8.5, "CREATININE": 3.2, "PLT": 180, "WBC": 7.5, "ALT": 35}
    }
  }' | python3 -m json.tool
```

Expected: Nephrology ~0.95, Hematology ~0.53, ER ~0.03

### Case 2: Healthy 35-year-old female

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "age": 35, "sex": "female",
      "values": {"HGB": 13.5, "CREATININE": 0.9, "PLT": 250, "WBC": 6.0, "ALT": 25}
    }
  }' | python3 -m json.tool
```

Expected: POZ ~0.82, all specialists low

### Case 3: ER trigger — WBC 32 + PLT 40

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "age": 45, "sex": "female",
      "values": {"HGB": 9.0, "WBC": 32.0, "PLT": 40.0}
    }
  }' | python3 -m json.tool
```

Expected: ER ~0.50, Hematology ~0.95

---

## How to switch to real BERT inference

When `checkpoints/finetune/` is ready, in `api/main.py` (lines 49–53):

```python
# BEFORE (mock):
from api.predict_mock import router as predict_mock_router
app.include_router(predict_mock_router)

# AFTER (real BERT) — uncomment the block at lines 127–175
# and remove the predict_mock_router include above.
# Set model_path = Path("checkpoints/finetune/") in startup().
```

When `ANTHROPIC_API_KEY` is available, replace `explain_mock_router` with a real
`api/explain.py` module that calls Opus 4.7 with the clinical context as system prompt.
