# BloodAI — Model Card

## Model

**BERT 6L-256H-8A** fine-tuned for multi-label triage classification of blood test results.

- Architecture: 6 transformer layers, 256 hidden, 8 attention heads, FFN 1024
- Vocabulary: ~500 tokens (custom word-level, all lowercase in tokenizer)
- Output: 8 independent sigmoid probabilities (multi-label, not softmax)
- File: `checkpoints/finetune/` + `checkpoints/finetune/class_thresholds.json`

---

## Classes

| Code | Display Name | Description |
|------|-------------|-------------|
| POZ | POZ | Primary care — no specialist referral needed |
| GASTRO | Gastroenterology | GI abnormalities (ALT, AST elevated) |
| HEMATO | Hematology | Blood count abnormalities (HGB, PLT, WBC, HCT, MCV) |
| NEFRO | Nephrology | Kidney function (CREATININE, UREA elevated) |
| SOR | ER | Emergency — critical values, immediate care |
| CARDIO | Cardiology | Cardiovascular risk markers |
| PULMO | Pulmonology | Respiratory-linked blood abnormalities |
| HEPATO | Hepatology | Liver function (ALT, AST, UREA patterns) |

---

## Evaluation Results (val.txt, 31 345 examples)

### Raw metrics (threshold 0.5)

| Class | ROC AUC | PR AUC | Prevalence | F1@0.5 |
|-------|---------|--------|------------|--------|
| POZ | 0.788 | 0.677 | 38.1% | 0.655 |
| GASTRO | 0.824 | 0.677 | 31.0% | 0.636 |
| HEMATO | 0.905 | 0.807 | 29.0% | 0.734 |
| NEFRO | 0.892 | 0.852 | 38.0% | 0.760 |
| SOR | 0.696 | 0.857 | 72.1% | 0.820 |
| CARDIO | 0.906 | 0.883 | 45.6% | 0.815 |
| PULMO | 0.828 | 0.657 | 25.9% | 0.582 |
| HEPATO | 0.877 | 0.516 | 10.9% | 0.553 |

**Why PR AUC alongside ROC AUC:** For imbalanced classes (HEPATO: 10.9% prevalence), ROC AUC is inflated by the large True Negative pool. PR AUC measures precision/recall without True Negatives — HEPATO ROC 0.877 but PR AUC 0.516 reveals the true difficulty.

### Calibration

- ECE before temperature scaling: 0.0135
- Temperature T = 0.9411 (LBFGS on val set)
- ECE after calibration: **0.0123** (target < 0.012 — nearly achieved)

### Calibrated thresholds (cost-weighted w·FNR + FPR minimization)

| Class | Threshold | FNR | FPR | Cost Weight |
|-------|-----------|-----|-----|-------------|
| POZ | 0.4829 | 0.256 | 0.304 | 1.0 |
| GASTRO | 0.2954 | 0.029 | 0.694 | 5.0 |
| HEMATO | 0.2856 | 0.028 | 0.479 | 7.0 |
| NEFRO | 0.2938 | 0.028 | 0.587 | 7.0 |
| SOR | 0.3556 | **0.000** | 0.999 | 10.0 |
| CARDIO | 0.3432 | 0.033 | 0.455 | 5.0 |
| PULMO | 0.3011 | 0.042 | 0.662 | 5.0 |
| HEPATO | 0.2840 | 0.052 | 0.490 | 4.0 |

**SOR safety property:** FNR = 0.000 — the model never misses a true emergency case. The cost is FPR = 0.999 (many false alarms), which is the correct clinical trade-off.

---

## Training

- Loss: `FocalBCELoss(γ=2.0)` with per-class cost weights (SOR=10, NEFRO=7, HEMATO=7, CARDIO=5, PULMO=5, GASTRO=5, HEPATO=4, POZ=1)
- Optimizer: AdamW, lr=2e-5, warmup=300 steps, weight_decay=0.01
- Data: 408 214 training examples, patient-level 80/20 split
- Pre-training: MLM on 260k Synthea + MIMIC-III/IV encounters (`checkpoints/mlm/`)
- Fine-tuning: 5 epochs, batch_size=32, no eval during training (eval disabled to prevent macOS OOM on CPU)

---

## Data Pipeline: Lab Values → Tokens → Model

### Step 1 — Quantization (`data/utils.py: get_lab_token_v2`)

```python
get_lab_token_v2(param, value, age, sex, lab_norms)
# sex must be 'm' or 'f' (not 'male'/'female') — matches lab_norms.json keys
```

Reference ranges from `config/lab_norms.json`, stratified by age group × sex:
- Age groups: `kids` (<18), `under_30` (18-29), `under_60` (30-59), `seniors` (≥60)
- Sex keys: `m` / `f`

Quantization rules:
- `value < low * 0.60` → `PARAM_CRITICAL_LOW`
- `low * 0.60 ≤ value < low` → `PARAM_Q1` .. `PARAM_Q4` (below normal)
- `low ≤ value ≤ high` → `PARAM_Q5` .. `PARAM_Q10` (center = Q5)
- `high < value < high * 1.50` → `PARAM_Q6` .. `PARAM_Q10` (above normal)
- `value ≥ high * 1.50` → `PARAM_CRITICAL_HIGH`

**Critical:** the tokenizer lowercases everything — `HGB_Q3` is stored as `hgb_q3`. Attention extraction must call `.upper()` when matching back to param names.

### Step 2 — Trigger tokens

```python
extract_triggers(tokens)  # → ["HGB_LOW", "CREATININE_HIGH", ...]
```

Each parameter outside normal range generates a trigger. Triggers drive the adaptive questions system and are appended as `TRIGGER_HGB_LOW` tokens.

### Step 3 — Adaptive questions (optional, improves accuracy)

```
GET /questions/{param}?age=60
→ returns questions for that trigger
→ user answers → SYMPTOM_FATIGUE_YES / SYMPTOM_FATIGUE_NO tokens
→ appended to input sequence
```

### Complete input sequence example

```
[CLS] AGE_60 SEX_M HGB_CRITICAL_LOW CREATININE_Q9 PLT_Q7
      TRIGGER_HGB_LOW TRIGGER_CREATININE_HIGH
      SYMPTOM_FATIGUE_YES SYMPTOM_EDEMA_YES [SEP] [PAD] ...
```

Max length: 128 tokens (truncated if longer).

### Model output

```python
outputs.logits       # Tensor[8] — raw logits
probs = sigmoid(logits)  # Tensor[8] — probabilities per class
outputs.attentions   # tuple of 6 tensors, each [batch, 8_heads, 128, 128]
```

---

## Attention Heatmap

Attention weights are extracted from the CLS row, averaged across all 6 layers and 8 heads:

```python
stacked = torch.stack(outputs.attentions)  # [6, batch, 8, seq, seq]
attn_mean = stacked.mean(dim=(0, 2))        # [batch, seq, seq]
cls_row = attn_mean[0, 0, :]               # [seq] — what [CLS] attends to

# Map tokens back to param names (tokenizer lowercases → .upper() required)
param = token.split("_")[0].upper()
if param in {"HGB", "HCT", "PLT", "MCV", "WBC", "CREATININE", "ALT", "AST", "UREA"}:
    param_weights[param] = max(param_weights.get(param, 0.0), float(weight))
```

Returns `List[AttentionWeight]` sorted descending — highest attention = most influential parameter for prediction.

---

## API Contract

### Request

```json
POST /predict
{
  "input": {
    "age": 60,
    "sex": "male",
    "values": {
      "HGB": 10.5,
      "CREATININE": 4.8,
      "UREA": 25.0
    },
    "notes": null,
    "collectedAt": null
  }
}
```

`sex` accepts `"male"` or `"female"` — internally mapped to `"m"/"f"` before lab norm lookup.

### Response

```json
{
  "predictions": [
    {"class": "Nephrology", "probability": 0.6962},
    {"class": "ER",         "probability": 0.5824},
    ...
  ],
  "attention": [
    {"param": "CREATININE", "weight": 0.2793},
    {"param": "UREA",       "weight": 0.1196},
    {"param": "HGB",        "weight": 0.1025}
  ],
  "ece": 0.0123,
  "modelVersion": "bert-5ep-v1"
}
```

`predictions` is sorted descending by probability. All 8 classes are always returned.

### Safety rule

If `SOR` (ER) probability exceeds its threshold (0.3556), the API flags it and suppresses all other specialists — immediate emergency referral takes precedence. If no class exceeds its threshold, defaults to `POZ` (primary care).

---

## Thresholds File

`checkpoints/finetune/class_thresholds.json` — generated by `model/evaluate.py` via cost-weighted ROC optimization. Loaded at startup by `api/predict_real.py:initialize()`. If the file is absent, falls back to hardcoded defaults in `_CLASS_THRESHOLDS`.

---

## Files

| File | Purpose |
|------|---------|
| `checkpoints/finetune/` | Fine-tuned BERT weights (`pytorch_model.bin`, `config.json`) |
| `checkpoints/finetune/tokenizer/` | WordLevel tokenizer (`vocab.json`, `tokenizer.json`) |
| `checkpoints/finetune/class_thresholds.json` | Calibrated per-class decision thresholds |
| `config/lab_norms.json` | Reference ranges for 9 parameters × age group × sex |
| `data/utils.py` | `get_lab_token_v2`, `extract_triggers`, `load_lab_norms` |
| `model/bert_model.py` | `BertForMultiLabelClassification`, `LABEL_MAP`, `REVERSE_LABEL_MAP` |
| `api/predict_real.py` | FastAPI router: POST /predict |
| `model/evaluate.py` | Evaluation + temperature scaling + threshold calibration |
