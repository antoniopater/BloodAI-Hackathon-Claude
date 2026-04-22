---
name: bloodai-day1-pipeline
description: "Dzień 1 hackathonu BloodAI: budowa pełnego ML pipeline od zera + FastAPI backend. Użyj tego skilla na start pracy, do kontroli postępu w ciągu dnia, i do self-assessment na koniec dnia."
---

# Dzień 1: Pipeline ML + Backend

## Cel dnia
Na koniec dnia masz: działający ML pipeline (preprocessing → tokenizer → MLM → fine-tuning) + FastAPI z endpointem `/predict` zwracającym 8 prawdopodobieństw i attention weights. Trening puszczony w nocy.

## Checklist zadań

### Blok 1: Setup (1-2h)
- [ ] `git init`, GitHub repo (PUBLICZNE), licencja MIT, `.gitignore`
- [ ] Struktura projektu:
```
bloodai/
├── data/           # skrypty do pobrania/generacji danych
├── model/          # architektura BERT, trening
├── api/            # FastAPI
├── frontend/       # React (dzień 2)
├── config/         # lab_norms.json, questions.json, icd_mapping.json
├── notebooks/      # eksploracja, ewaluacja
├── README.md
└── requirements.txt
```
- [ ] `requirements.txt`: torch, transformers, fastapi, uvicorn, pandas, scikit-learn, matplotlib
- [ ] README.md — krótki opis projektu, architektura, setup

### Blok 2: Data Pipeline (2-3h)
- [ ] Skrypt `data/prepare_corpus.py`:
  - Pobierz/wygeneruj dane Synthea (jeśli nie masz MIMIC: sam Synthea wystarczy na hackathon)
  - Preprocessing: ekstrakcja lab values, demographics, ICD codes
  - Kwantyzacja lab values → tokeny (HGB_Q1..Q10, CREATININE_Q1..Q10, _CRITICAL_LOW, _CRITICAL_HIGH)
  - ICD → label mapping (8 klas)
  - Patient-level split: 80/20 train/val (ten sam pacjent nigdy w obu)
  - Output: `train.txt`, `val.txt` — sequences of tokens + labels
- [ ] `config/lab_norms.json` — normy referencyjne z podziałem na wiek/płeć
- [ ] `config/questions.json` — bank pytań adaptive interview
- [ ] `config/icd_mapping.json` — ICD code → specjalizacja

### Blok 3: Model + Trening (2-3h)
- [ ] `model/tokenizer.py` — word-level tokenizer, vocab ~140, special tokens [PAD] [UNK] [CLS] [SEP] [MASK]
- [ ] `model/bert_model.py` — BertConfig + BertForMaskedLM (6 layers, 256 hidden, 8 heads, FFN 1024)
- [ ] `model/pretrain_mlm.py` — MLM pre-training:
  - Mask 15% tokenów
  - AdamW, lr=1e-4, batch 64, do 15 epochs
  - Save checkpoint co epoch
- [ ] `model/finetune_multilabel.py` — Multi-label fine-tuning:
  - [CLS] → Linear(256, 8) → Sigmoid
  - BCEWithLogitsLoss + cost-sensitive focal loss
  - Clinical cost matrix (SOR miss = 10, specialist confusion = 5-7)
  - AdamW, lr=2e-5, batch 32, do 5 epochs
  - Per-class threshold tuning (Youden's index)
  - Save: model + thresholds + tokenizer
- [ ] `model/evaluate.py` — ROC AUC, AUPRC, ECE, confusion matrices per class
- [ ] Puścić trening: MLM → fine-tuning (łącznie ~2-4h na GPU)

### Blok 4: FastAPI (1-2h)
- [ ] `api/main.py`:
```python
@app.post("/predict")
# Input: {age: 60, sex: "M", hgb: 6.5, hct: 19, plt: 45, ...}
# Output: {probabilities: {poz: 0.15, hema: 0.85, neph: 0.92, sor: 0.95, ...},
#          attention: {hgb: 0.87, creatinine: 0.68, ...},
#          flags: ["SOR", "Hematologia", "Nefrologia"]}

@app.get("/lab_norms")
# Zwraca normy referencyjne

@app.get("/questions/{param}")
# Zwraca pytanie z banku dla danego parametru poza normą
```
- [ ] Załadować model z checkpointu (lazy loading, singleton)
- [ ] Test: `curl -X POST localhost:8000/predict -d '{"age":60,"sex":"M","creatinine":4.8,...}'`

## Self-assessment na koniec dnia

Odpowiedz na każde pytanie 1-5:

| Pytanie | Score |
|---------|-------|
| Czy pipeline preprocessingu działa end-to-end? (dane → tokeny → split) | /5 |
| Czy trening został uruchomiony i produkuje sensowne logi? | /5 |
| Czy FastAPI `/predict` zwraca poprawne predykcje? | /5 |
| Czy repo jest na GitHubie z sensownym README? | /5 |
| Czy struktura kodu jest czysta i dobrze zorganizowana? | /5 |

**25/25** = idealnie, jutro budujesz frontend na solidnym fundamencie
**20-24** = dobrze, drobne luki do uzupełnienia rano
**15-19** = trzeba nadrobić jutro rano przed frontendem
**<15** = zredukuj scope — uprość pipeline, skup się na działającym `/predict`

## Fallback jeśli brakuje czasu
Jeśli nie masz GPU lub trening trwa za długo:
1. Użyj mniejszego datasetu (10k sampli zamiast 260k)
2. Zmniejsz epochs (MLM: 5, fine-tune: 3)
3. W ostateczności: uprość model do logistic regression na tokenach — nadal multi-label, nadal valid
4. NIGDY nie fałszuj metryk — lepsza prawdziwa słabsza metryka niż zmyślona dobra

## Committy
- `init: project structure and requirements`
- `data: preprocessing pipeline and tokenizer`
- `model: BERT architecture and MLM pre-training`
- `model: multi-label fine-tuning with focal loss`
- `api: FastAPI predict endpoint`
