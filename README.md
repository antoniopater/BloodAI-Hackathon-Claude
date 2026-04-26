# BloodAI — Intelligent Multi-Label Triage

> Snap a photo of a blood test → AI explains what's abnormal, which specialist to see, and where to book. From‑scratch domain BERT (val ECE 0.012, 8‑class triage) + Claude Opus 4.7 for vision OCR / explanations / trend narrative + live NFZ queue API + Google Places.

Built solo for the **Built with Opus 4.7** hackathon (Cerebral Valley).

---

## What it does

1. **Scan** a blood test printout (photo or PDF) — Opus 4.7 Vision OCR extracts values + reference ranges.
2. **Triage** with a domain‑specific BERT (6L · 8H · 256d · vocab 179) trained on 408k Synthea + MIMIC sequences. Returns 8 calibrated probabilities + per‑parameter attention.
3. **Explain** the result in plain English (patient mode) or as a structured clinical note (clinical mode), with red flags and 3–6 follow‑up tests.
4. **Track trends** over multiple visits — linear regression per parameter, 6 cross‑parameter comorbidity detectors (CKD progression, hepatocellular injury, bone‑marrow suppression, …) and an Opus narrative.
5. **Find a doctor** — live NFZ queue API (Polish public health) + Google Places for private clinics, with haversine distance ranking.

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/<your-fork>/BloodAI-Hackathon-Claude.git
cd BloodAI-Hackathon-Claude
```

### 2. Create your `.env` file (IMPORTANT — read this carefully)

The backend needs API keys to run. They are **never** committed (`.env` is in `.gitignore`).

```bash
cp .env.example .env
```

Then open `.env` in your editor and replace the placeholders:

| Variable | Required? | Where to get it |
|----------|-----------|-----------------|
| `ANTHROPIC_API_KEY` | **Yes** | <https://console.anthropic.com/settings/keys> — create a key, paste it. Used by `/scan`, `/explain`, `/trends`. |
| `GOOGLE_MAPS_API_KEY` | Optional | <https://console.cloud.google.com/apis/credentials> — create a key, then **enable** the *Places API* and *Geocoding API* on the same project. Without it `/doctors` returns an empty list (NFZ public clinics still work). |
| `BLOODAI_MODEL_ID` | No | Defaults to `claude-opus-4-7`. |
| `BLOODAI_PROMPT_VERSION` | No | Defaults to `v1` (loads `prompts/scan_v1.md`). |
| `USE_OPUS_API` | No | Set to `false` to run the backend fully offline — `/scan` and `/explain` return mock JSON, `/trends` falls back to a rule‑based narrative. Useful for development. |

Example (with everything filled in):

```env
ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GOOGLE_MAPS_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
BLOODAI_MODEL_ID=claude-opus-4-7
BLOODAI_PROMPT_VERSION=v1
USE_OPUS_API=true
```

> ⚠️ **Never commit `.env` or paste a real API key into a public file.** If you accidentally pushed one, rotate the key immediately in the provider console.

### 3. Backend — Python deps

```bash
# (recommended) create a virtualenv
python3 -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Model checkpoint

The repo already ships with a fine‑tuned BERT at `checkpoints/finetune/` (18 MB, val ECE 0.012). Nothing to download.

If you want to retrain from scratch see [Training the model](#training-the-model) below.

### 5. Run the backend

```bash
USE_TF=0 PYTHONPATH=. uvicorn api.main:app --reload --port 4000
```

> `USE_TF=0` is required on macOS Anaconda — otherwise transformers eagerly imports TensorFlow which deadlocks on the macOS mutex.

The API is now live at <http://127.0.0.1:4000> (docs at `/docs`).

Smoke test:

```bash
curl http://127.0.0.1:4000/health
# {"status":"ok","model_loaded":true,"model":"bert-5ep-v1"}
```

### 6. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The frontend proxies `/api/*` to the backend on port 4000 (see `frontend/vite.config.ts`).

---

## Endpoints

All live, all unit‑tested. Full schemas at `/docs`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/scan` | Opus 4.7 Vision OCR — image → `{values, confidence, rawText}` |
| `POST` | `/predict` | BERT triage — labs → 8 probs + per‑parameter attention + ECE |
| `POST` | `/explain` | Opus 4.7 patient/clinical summary + red flags + 3–6 suggested tests |
| `POST` | `/trends` | Linear regression + 6 comorbidity patterns + Opus narrative |
| `POST` | `/compute_triggers` | Lab values → triggers + matching adaptive interview questions |
| `POST` | `/recommendations/tests` | Personalised follow‑up test list with NFZ‑cost / fasting / conditional logic |
| `GET`  | `/nfz/queues` | Live proxy to `api.nfz.gov.pl` — clinic queues + wait times |
| `GET`  | `/doctors` | Google Places — private specialists ranked by haversine distance |
| `GET`  | `/lab_norms` | 9 params × 4 age groups × 2 sexes reference ranges |
| `GET`  | `/questions/{param}` | Adaptive interview bank filtered by trigger + age |
| `GET`  | `/health` | Backend health + model load state |

---

## Architecture

```
data/
├── prepare_corpus.py       # Synthea + MIMIC preprocessing
├── utils.py                # Lab tokenization, age groups, triggers
├── train.txt / val.txt     # 408k + 31k tokenised sequences
└── questions.json          # 52 adaptive interview questions

model/
├── tokenizer.py            # Word-level tokenizer (vocab 179)
├── bert_model.py           # 6L · 8H · 256d BERT, multi-label head
├── losses.py               # Cost-sensitive focal loss (ER × 10)
├── pretrain_mlm.py         # MLM pre-training (15 epochs)
├── finetune_multilabel.py  # Multi-label fine-tuning (5 epochs)
└── evaluate.py             # ROC, PR, ECE, temperature scaling

api/
├── main.py                 # FastAPI app, routes, startup
├── predict_real.py         # BERT inference
├── explain_real.py         # Opus 4.7 explanations
├── scan.py                 # Opus 4.7 Vision OCR
├── trends.py               # Trend analysis + comorbidity patterns
├── nfz.py                  # NFZ queue proxy
├── doctors.py              # Google Places integration
└── recommended_tests.py    # Follow-up test recommendations

config/
├── lab_norms.json          # 9 params × 4 age groups × 2 sexes
├── medical_context.json    # Critical thresholds, CKD staging, comorbidities
├── recommended_tests.json  # 37 tests across 8 specialties (23 always + 14 conditional)
├── icd_mapping.json        # ICD-10 codes → 8 specialty classes
└── questions.json          # Adaptive interview rules

frontend/
└── src/
    ├── components/         # 34 .tsx — Screens, Medical, DoctorFinder, UI, Layout
    ├── hooks/              # 8 hooks (BERT, geolocation, lab norms, NFZ, Opus, trends, …)
    ├── services/           # axios clients (apiClient, bertClient, nfzClient, opusClient)
    └── store/useAppStore.ts # Zustand — history, lab norms, login, geolocation
```

---

## Classes (8 specialties) and calibration

| Code | Specialty | Threshold |
|------|-----------|-----------|
| `SOR`    | Emergency Department          | 0.356 |
| `NEFRO`  | Nephrology (kidneys)          | 0.294 |
| `HEMATO` | Hematology (blood disorders)  | 0.286 |
| `CARDIO` | Cardiology (heart)            | 0.343 |
| `PULMO`  | Pulmonology (lungs)           | 0.301 |
| `GASTRO` | Gastroenterology              | 0.295 |
| `HEPATO` | Hepatology (liver)            | 0.284 |
| `POZ`    | Primary care (routine)        | 0.483 |

Per‑class thresholds calibrated on the validation set (not a flat 0.5). Val **ECE = 0.0123**. SOR overrides every other flag (safety rule).

---

## Key design decisions

- **From‑scratch BERT, not a fine‑tuned LLM.** 18 MB model, vocab 179 tokens, runs on CPU in milliseconds.
- **Multi‑label.** Patients can have multiple simultaneous conditions (anemia + kidney failure).
- **Cost‑sensitive focal loss.** ER misses penalised 10×.
- **Patient‑level split.** Train and validation never share a patient (4 682 train / 1 171 val Synthea + 211k train / 30k val MIMIC encounters).
- **Adaptive interview, vocab‑aware.** 52 follow‑up questions; the backend silently drops the 43 OOV tokens and keeps the 25 in‑vocab ones, empirically shifting BERT predictions by 21–49 percentage points (verified A/B in `test_adaptive_impact.py`).
- **Trend detection beyond 2‑point deltas.** Linear regression with R², acceleration check, threshold crossing, and 6 cross‑parameter comorbidity signatures.
- **Opus 4.7 used in 4 places, not just chat.** Vision OCR (versioned prompt + Polish‑decimal retry), patient explanation, clinical assessment, trend narrative — all return validated JSON with rule‑based fallbacks.

---

## Training the model

The repo already includes a trained checkpoint, so this is only needed if you want to reproduce or change the architecture.

```bash
# 1. Generate Synthea data (or download a release)
cd data/synthea
git clone https://github.com/synthetichealth/synthea.git
cd synthea && ./run_synthea.sh -s 12345 -p 5000 -a 40 -g

# 2. Drop MIMIC-III/IV csv.gz files into data/mimic/hosp/ (requires PhysioNet credentialing)

# 3. Build the corpus
python data/prepare_corpus.py --synthea-dir data/synthea/ --mimic-dir data/mimic/hosp/

# 4. MLM pre-training (~overnight on a single GPU)
python model/pretrain_mlm.py --corpus data/train.txt --output checkpoints/mlm/ --epochs 15

# 5. Fine-tune for triage (~hours)
python model/finetune_multilabel.py \
  --pretrained checkpoints/mlm/ \
  --output checkpoints/finetune/ \
  --epochs 5

# 6. Calibrate thresholds + evaluate
python model/evaluate.py --model checkpoints/finetune/
```

Targets reported in the underlying paper: ECE < 0.012, SOR ROC AUC ≈ 1.00, Nephrology ≈ 0.95, Hematology ≈ 0.94.

---

## Testing

```bash
# Backend: pytest unit tests
pytest tests/

# Live A/B on the running model — does the adaptive interview move predictions?
USE_TF=0 PYTHONPATH=. uvicorn api.main:app --port 4000 &
python test_adaptive_impact.py        # 6 cases, avg max |Δ| = 0.234
python test_known_vs_unknown.py        # known tokens 215 171× stronger than OOV
python test_predict_endpoint.py        # /predict schema + safety rules
```

---

## Project rules (hackathon)

- ✅ MIT licensed, fully open source
- ✅ All work new (started during the hackathon, not copied)
- ✅ Solo project
- ✅ No stolen code, data, or assets

---

## Documentation

- Full functionality audit: [`FUNCTIONALITY_REPORT.md`](FUNCTIONALITY_REPORT.md)
- Project rules and daily plan: [`CLAUDE.md`](CLAUDE.md)
- Day‑by‑day skills: [`skills/`](skills/)
- Source paper: [`docs/paper.pdf`](docs/paper.pdf)

---

## Citation

```
@inproceedings{bloodai2026,
  title  = {BloodAI: Intelligent Multi-Label Triage for Hematological Comorbidities},
  author = {Antonio Pater},
  booktitle = {Built with Opus 4.7 Hackathon},
  year   = {2026}
}
```

MIT License. See [`LICENSE`](LICENSE).
