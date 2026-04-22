# BloodAI — Intelligent Multi-Label Triage System

**Problem:** Patients receive blood test results they don't understand and don't know which specialist to see.

**Solution:** Scan a blood test printout → AI explains results → suggests which specialist → shows NFZ/private doctor queues with wait times.

**Tech Stack:**
- **ML Pipeline:** BERT (6L/256H/8A) with multi-label classification, MLM pre-training, focal loss
- **Frontend:** React (coming Day 2-5)
- **Backend:** FastAPI + PyTorch
- **API Layer:** claude-opus-4-7 for OCR, explanations, trend analysis
- **Data:** Synthea (synthetic) + MIMIC-IV (real hospital data)

---

## Quick Start

### 1. Setup

```bash
pip install -r requirements.txt
mkdir -p data/synthea data/mimic/hosp
```

Place your data in:
- `data/synthea/batch_*/csv/{patients,observations,conditions}.csv`
- `data/mimic/hosp/{patients,diagnoses_icd,labevents}.csv.gz`

### 2. Generate Synthea Test Data

For quick testing (without full MIMIC):
```bash
# Using synthea-java or Python Synthea generator
cd data/synthea
git clone https://github.com/synthetichealth/synthea.git
cd synthea && ./run_synthea.sh -s 12345 -p 100 -a 40 -g  # 100 synthetic patients
```

Or download pre-generated: https://github.com/synthetichealth/synthea/releases

### 3. Preprocess Data

```bash
python data/prepare_corpus.py \
  --synthea-dir data/synthea/ \
  --output data/corpus.txt
```

Outputs: `data/corpus.txt` with tokenized sequences.

### 4. MLM Pre-training

Build tokenizer and train BERT on corpus (runs overnight):

```bash
python model/pretrain_mlm.py \
  --corpus data/corpus.txt \
  --output checkpoints/mlm/ \
  --epochs 15
```

Outputs:
- `checkpoints/mlm/model.safetensors` — pre-trained BERT
- `checkpoints/mlm/tokenizer/` — word-level tokenizer

### 5. Fine-tuning for Multi-Label Triage

Train classifier with cost-sensitive focal loss (ER miss = 10):

```bash
python model/finetune_multilabel.py \
  --pretrained checkpoints/mlm/ \
  --corpus data/corpus.txt \
  --output checkpoints/finetune/ \
  --epochs 5
```

Outputs: `checkpoints/finetune/` with trained model.

### 6. Evaluate

Compute ECE, ROC AUC per class, apply temperature scaling:

```bash
python model/evaluate.py \
  --model checkpoints/finetune/ \
  --corpus data/corpus.txt
```

**Expected results:**
- ECE < 0.012 ✓ (calibration)
- SOR ROC AUC ≈ 1.00 ✓ (emergency detection)
- Nephrology ROC AUC ≈ 0.95 ✓
- Haematology ROC AUC ≈ 0.94 ✓

### 7. Run API Server

```bash
uvicorn api.main:app --reload --port 8000
```

### 8. Test API

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "age": 60,
    "sex": "M",
    "hgb": 6.5,
    "hct": 19,
    "plt": 45,
    "wbc": 15,
    "creatinine": 4.8,
    "alt": 80
  }'
```

**Response:**
```json
{
  "flags": ["SOR", "HEMATO", "NEFRO"],
  "probabilities": {
    "POZ": 0.02,
    "GASTRO": 0.15,
    "HEMATO": 0.87,
    "NEFRO": 0.92,
    "SOR": 0.98,
    "CARDIO": 0.35,
    "PULMO": 0.20,
    "HEPATO": 0.12
  },
  "attention": {"HGB_CRITICAL_LOW": 0.89, "CREATININE_Q9": 0.68, ...},
  "tokens": ["AGE_60", "SEX_M", "HGB_CRITICAL_LOW", ...]
}
```

---

## Architecture

```
data/
├── prepare_corpus.py      ← Synthea + MIMIC preprocessing
├── utils.py               ← Lab tokenization, age groups, triggers
└── synthea/, mimic/       ← Raw data (gitignored)

model/
├── tokenizer.py           ← Build/load word-level tokenizer
├── bert_model.py          ← 6L/256H/8A BERT, multi-label head
├── losses.py              ← Focal loss, ECE loss
├── pretrain_mlm.py        ← MLM pre-training script
├── finetune_multilabel.py ← Multi-label fine-tuning (focal loss)
└── evaluate.py            ← Metrics, temperature scaling

api/
└── main.py                ← FastAPI endpoints

config/
├── lab_norms.json         ← Reference ranges per age/sex
├── icd_mapping.json       ← ICD codes → 8 classes
└── questions.json         ← Adaptive interview bank
```

---

## Classes (8 Specialties)

1. **POZ** — Primary care (routine)
2. **GASTRO** — Gastroenterology
3. **HEMATO** — Hematology (blood disorders)
4. **NEFRO** — Nephrology (kidneys)
5. **SOR** — Emergency (ICU-level urgency)
6. **CARDIO** — Cardiology (heart)
7. **PULMO** — Pulmonology (lungs)
8. **HEPATO** — Hepatology (liver)

---

## Key Design Decisions

- **Multi-label:** Patient can have multiple simultaneous conditions (anemia + kidney failure)
- **Cost-sensitive:** SOR (emergency) misses heavily penalized (weight = 10)
- **Patient-level split:** Train/val never share same patient (avoid data leakage)
- **Focal loss:** Focuses on hard/borderline cases, not easy examples
- **ECE calibration:** Probabilities trustworthy for clinical use (< 0.012 error)
- **Attention:** Shows which parameters drove decision (explainability)

---

## Project Rules

- ✅ Everything open source (MIT license)
- ✅ All work NEW (started during hackathon, not copied)
- ✅ Solo project
- ✅ No stolen code/data/assets

---

## Documentation

- Full plan: [`docs/hackathon-plan.md`](docs/hackathon-plan.md)
- Project rules: [`CLAUDE.md`](CLAUDE.md)
- Daily skills & checklists: [`skills/`](skills/)
- Research paper: [`docs/paper.pdf`](docs/paper.pdf)

---

## Citation

If you use this code or data, cite:

```
@inproceedings{bloodai2026,
  title={BloodAI: Intelligent Multi-Label Triage for Hematological Comorbidities},
  author={Antonio Pater},
  booktitle={Built with Opus 4.7 Hackathon},
  year={2026}
}
```

MIT License. See `LICENSE`.
