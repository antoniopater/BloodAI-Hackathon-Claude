---
name: bloodai-day1-pipeline
description: "BloodAI hackathon Day 1: build the full ML pipeline from scratch + FastAPI backend. Use at day start, for progress checks during the day, and for end-of-day self-assessment."
---

# Day 1: ML Pipeline + Backend

## Goal for the day
By end of day: working ML pipeline (preprocessing → tokenizer → MLM → fine-tuning) + FastAPI with `/predict` returning 8 probabilities and attention weights. Training kicked off for overnight run.

## Task checklist

### Block 1: Setup (1–2h)
- [ ] `git init`, GitHub repo (PUBLIC), MIT license, `.gitignore`
- [ ] Project structure:
```
bloodai/
├── data/           # scripts to download/generate data
├── model/          # BERT architecture, training
├── api/            # FastAPI
├── frontend/       # React (day 2)
├── config/         # lab_norms.json, questions.json, icd_mapping.json
├── notebooks/      # exploration, evaluation
├── README.md
└── requirements.txt
```
- [ ] `requirements.txt`: torch, transformers, fastapi, uvicorn, pandas, scikit-learn, matplotlib
- [ ] README.md — short project description, architecture, setup

### Block 2: Data Pipeline (2–3h)
- [ ] Script `data/prepare_corpus.py`:
  - Download/generate Synthea data (if no MIMIC: Synthea alone is enough for the hackathon)
  - Preprocessing: extract lab values, demographics, ICD codes
  - Quantize lab values → tokens (HGB_Q1..Q10, CREATININE_Q1..Q10, _CRITICAL_LOW, _CRITICAL_HIGH)
  - ICD → label mapping (8 classes)
  - Patient-level split: 80/20 train/val (same patient never in both)
  - Output: `train.txt`, `val.txt` — sequences of tokens + labels
- [ ] `config/lab_norms.json` — reference ranges by age/sex
- [ ] `config/questions.json` — adaptive interview question bank
- [ ] `config/icd_mapping.json` — ICD code → specialty

### Block 3: Model + Training (2–3h)
- [ ] `model/tokenizer.py` — word-level tokenizer, vocab ~140, special tokens <PAD> <UNK> [CLS] [SEP] [MASK]
- [ ] `model/bert_model.py` — BertConfig + BertForMaskedLM (6 layers, 256 hidden, 8 heads, FFN 1024)
- [ ] `model/pretrain_mlm.py` — MLM pre-training:
  - Mask 15% of tokens
  - AdamW, lr=1e-4, batch 64, up to 15 epochs
  - Save checkpoint each epoch
- [ ] `model/finetune_multilabel.py` — Multi-label fine-tuning:
  - [CLS] → Linear(256, 8) → Sigmoid
  - BCEWithLogitsLoss + cost-sensitive focal loss
  - Clinical cost matrix (ER miss = 10, specialist confusion = 5–7)
  - AdamW, lr=2e-5, batch 32, up to 5 epochs
  - Per-class threshold tuning (Youden's index)
  - Save: model + thresholds + tokenizer
- [ ] `model/evaluate.py` — ROC AUC, AUPRC, ECE, confusion matrices per class
- [ ] Run training: MLM → fine-tuning (~2–4h on GPU total)

### Block 4: FastAPI (1–2h)
- [ ] `api/main.py`:
```python
@app.post("/predict")
# Input: {age: 60, sex: "M", hgb: 6.5, hct: 19, plt: 45, ...}
# Output: {probabilities: {poz: 0.15, hema: 0.85, neph: 0.92, sor: 0.95, ...},
#          attention: {hgb: 0.87, creatinine: 0.68, ...},
#          flags: ["ER", "Hematology", "Nephrology"]}

@app.get("/lab_norms")
# Returns reference ranges

@app.get("/questions/{param}")
# Returns question from bank for out-of-range parameter
```
- [ ] Load model from checkpoint (lazy loading, singleton)
- [ ] Test: `curl -X POST localhost:8000/predict -d '{"age":60,"sex":"M","creatinine":4.8,...}'`

## End-of-day self-assessment

Answer each question 1–5:

| Question | Score |
|----------|-------|
| Does the preprocessing pipeline work end-to-end? (data → tokens → split) | /5 |
| Was training started and producing sensible logs? | /5 |
| Does FastAPI `/predict` return correct predictions? | /5 |
| Is the repo on GitHub with a sensible README? | /5 |
| Is the code structure clean and well organized? | /5 |

**25/25** = ideal; tomorrow you build the frontend on a solid base  
**20–24** = good; small gaps to fill in the morning  
**15–19** = catch up tomorrow morning before frontend  
**<15** = reduce scope — simplify pipeline, focus on working `/predict`

## Fallback if time runs out
If you have no GPU or training takes too long:
1. Use a smaller dataset (10k samples instead of 260k)
2. Fewer epochs (MLM: 5, fine-tune: 3)
3. Last resort: simplify to logistic regression on tokens — still multi-label, still valid
4. NEVER fake metrics — a weaker real metric beats a made-up good one

## Commit message ideas
- `init: project structure and requirements`
- `data: preprocessing pipeline and tokenizer`
- `model: BERT architecture and MLM pre-training`
- `model: multi-label fine-tuning with focal loss`
- `api: FastAPI predict endpoint`
