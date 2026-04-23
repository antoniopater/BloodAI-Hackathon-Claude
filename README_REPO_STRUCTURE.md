# BloodAI — Struktura Repozytorium

## 📂 Sekcje główne

### `api/` — Backend (FastAPI)
- `main.py` — endpoints /predict, /lab_norms, /questions
- `normalizer.py` — normalizacja wartości lab (T-score, Z-score)
- `scan.py` — OCR skanu (Opus 4.7 Vision) + extract lab values

### `model/` — ML Pipeline (PyTorch + HuggingFace)
- `tokenizer.py` — word-level tokenizer z corpus
- `bert_model.py` — BertForMultiLabelClassification (8 klas)
- `losses.py` — FocalBCELoss + cost matrix
- `pretrain_mlm.py` — MLM pre-training (15 epok)
- `finetune_multilabel.py` — Fine-tuning na 8 klasach (5 epok)
- `evaluate.py` — ROC, PR, ECE, kalibracja progów

### `data/` — Corpus + Konfiguracja
- `prepare_corpus.py` — generator corpus z Synthea + MIMIC-III/IV
- `utils.py` — utilities: get_lab_token_v2, load_questions_bank, etc.
- `train.txt`, `val.txt`, `mimic_test.txt` — corpus (gitignored, generowane)
- `lab_norms.json` — reference ranges dla każdego lab parametru
- `questions.json` — adaptive interview questions per trigger

### `config/` — Stałe i Mapy
- `icd_mapping.json` — ICD-10 → clinical specialty mapping
- `snomed_mapping.json` — SNOMED-CT → clinical specialty mapping

### `checkpoints/` — Model Weights (gitignored)
- `checkpoints/mlm/` — pre-trained BERT z MLM
- `checkpoints/finetune/` — fine-tuned model + class_thresholds.json

### `frontend/` — React/Next.js UI
- TBD: Form → POST /predict → Triage results

### `docs/` — Dokumentacja
- `paper.pdf` — paper naukowy (referencja)
- `ML_PIPELINE.md` — kompletna dokumentacja pipeline'u
- `METHODOLOGY_CHECKLIST.md` — checklist badań / publikacji
- `METHODOLOGY_REVIEW.md` — review paper

### `skills/` — Hackathon Checklist
- `day1-pipeline/` — ML pipeline + API
- `day2-frontend/` — React UI
- `day3-opus/` — Opus 4.7 integration
- `day4-nfz-dualmode/` — NFZ API + dual mode
- `day5-demo/` — Deploy + pitch
- `scoring/` — self-assessment

### `tests/` — Unit Tests
- TBD: test_tokenizer.py, test_predict.py, etc.

### `notebooks/` — Exploratory
- TBD: EDA, hyperparameter tuning, visualizations

### `prompts/` — System Prompts
- TBD: Opus 4.7 scan, explanation, second opinion

---

## 🚀 Quick Start

### 1. Regenerate Corpus (once)
```bash
USE_TF=0 PYTHONPATH="." python data/prepare_corpus.py
```

### 2. MLM Pre-training
```bash
USE_TF=0 PYTHONUNBUFFERED=1 PYTHONPATH="." python model/pretrain_mlm.py \
  --corpus data/train.txt --output checkpoints/mlm/
```

### 3. Fine-tuning
```bash
USE_TF=0 PYTHONPATH="." python model/finetune_multilabel.py \
  --pretrained checkpoints/mlm/ \
  --train-corpus data/train.txt \
  --val-corpus data/val.txt \
  --output checkpoints/finetune/
```

### 4. Evaluate + Calibrate
```bash
USE_TF=0 PYTHONPATH="." python model/evaluate.py \
  --model checkpoints/finetune/ \
  --corpus data/mimic_test.txt
```

### 5. Run API
```bash
uvicorn api.main:app --reload --port 8000
```

---

## 📊 Key Metrics

- **MLM eval_loss**: <0.65 (perplexity)
- **Fine-tune ROC-AUC**: >0.85 per class
- **ECE (Expected Calibration Error)**: <0.012
- **Latency**: /predict <100ms (CPU), <20ms (GPU)

---

## 🔧 Environment

- Python: `/opt/anaconda3/bin/python` (Anaconda 3.12)
- PyTorch CPU
- Dependencies: `pip install -r requirements.txt`
- **Critical**: `USE_TF=0` env var (TensorFlow mutex deadlock fix)

---

## 📝 Commits

- Frequent, meaningful commits with clear messages
- Format: `type: subject` (fix, feat, docs, refactor, etc.)
