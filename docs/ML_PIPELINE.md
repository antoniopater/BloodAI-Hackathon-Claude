# BloodAI — ML Pipeline: Kompletna Dokumentacja

## Spis treści

1. [Przegląd pipeline'u](#1-przegląd-pipelineu)
2. [Słownik tokenów — język modelu](#2-słownik-tokenów--język-modelu)
3. [Etap 0: Przygotowanie corpus](#3-etap-0-przygotowanie-corpus)
4. [Etap 1: Budowa tokenizera](#4-etap-1-budowa-tokenizera)
5. [Etap 2: MLM Pretraining](#5-etap-2-mlm-pretraining)
6. [Etap 3: Fine-tuning (klasyfikacja)](#6-etap-3-fine-tuning-klasyfikacja)
7. [Etap 4: Ewaluacja i kalibracja](#7-etap-4-ewaluacja-i-kalibracja)
8. [Etap 5: API — wdrożenie](#8-etap-5-api--wdrożenie)
9. [Architektura BERT — szczegóły](#9-architektura-bert--szczegóły)
10. [Jak testować każdy etap](#10-jak-testować-każdy-etap)
11. [Typowe błędy i diagnostyka](#11-typowe-błędy-i-diagnostyka)

---

## 1. Przegląd pipeline'u

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DANE ŹRÓDŁOWE                               │
│   Synthea (SNOMED) ──┐                                              │
│                      ├──► data/prepare_corpus.py                    │
│   MIMIC-III/IV (ICD) ┘                                              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    train.txt / val.txt / mimic_test.txt
                                 │
                    ┌────────────▼────────────┐
                    │  ETAP 1: TOKENIZER      │
                    │  model/tokenizer.py     │
                    │  WordLevel, vocab≈143   │
                    └────────────┬────────────┘
                                 │ checkpoints/mlm/tokenizer/
                    ┌────────────▼────────────┐
                    │  ETAP 2: MLM PRETRAINING│
                    │  model/pretrain_mlm.py  │
                    │  BertForMaskedLM        │
                    │  15% masking, 15 epochs │
                    └────────────┬────────────┘
                                 │ checkpoints/mlm/
                    ┌────────────▼────────────┐
                    │  ETAP 3: FINE-TUNING    │
                    │  model/finetune_        │
                    │  multilabel.py          │
                    │  FocalBCELoss, 8 klas   │
                    └────────────┬────────────┘
                                 │ checkpoints/finetune/
                    ┌────────────▼────────────┐
                    │  ETAP 4: EWALUACJA      │
                    │  model/evaluate.py      │
                    │  Temp scaling + ROC     │
                    │  → class_thresholds.json│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  ETAP 5: API            │
                    │  api/main.py (FastAPI)  │
                    │  POST /predict          │
                    └─────────────────────────┘
```

**Kluczowa idea**: model nie przetwarza liczb — przetwarza **tokeny semantyczne**. Wartość HGB=9.5 g/dL staje się tokenem `HGB_Q5` (wyraźnie poniżej normy dla seniora M). Dzięki temu BERT uczy się relacji między tokenami, a nie regresji na liczbach ciągłych.

---

## 2. Słownik tokenów — język modelu

Każda sekwencja treningowa to zdanie w specjalnym języku medycznym. Przykład pełnej sekwencji:

```
AGE_60 SEX_M HGB_Q5 CREATININE_Q9 PLT_Q7 TRIGGER_HGB_LOW
TRIGGER_CREATININE_HIGH SYMPTOM_GI_BLEED_YES SYMPTOM_WEIGHT_LOSS_NO
SYMPTOM_CHEST_PAIN_NO TARGET_GASTRO,NEFRO
```

### 2.1 Tokeny demograficzne

| Token | Znaczenie | Generowany przez |
|---|---|---|
| `AGE_10` .. `AGE_90` | Wiek w dekadach (int(age/10)*10) | `prepare_corpus.py` |
| `SEX_M` / `SEX_F` | Płeć | `prepare_corpus.py` |

> **Dlaczego dekady a nie dokładny wiek?** Zmniejsza rozmiar słownika (9 tokenów zamiast 100+), wymusza generalizację (model nie zapamiętuje konkretnych lat).

### 2.2 Tokeny laboratoryjne — kwantyzacja

Plik: `data/utils.py`, funkcja `get_lab_token_v2(test_name, value, age, sex, norms_db)`

```
WARTOŚĆ BADANIA
     │
     ▼
Wczytaj normę z config/lab_norms.json
(age_group + sex → {low, high})
     │
     ├── value < low * 0.6  →  {TEST}_CRITICAL_LOW
     │
     ├── value < low        →  {TEST}_Q1 .. Q5
     │   (Q1 = lekko poniżej, Q5 = mocno poniżej)
     │   Formuła: q = min(5, max(1, int((low-val)/q_width)+1))
     │   q_width = (high - low) / 10
     │
     ├── value ≤ high       →  {TEST}_Q5 .. Q10
     │   (Q5 = dół normy, Q10 = góra normy)
     │   Formuła: q = min(10, 5 + int((val-low)/q_width))
     │
     ├── value < high * 1.5 →  {TEST}_Q6 .. Q10
     │   (lekko powyżej normy)
     │
     └── value ≥ high * 1.5 →  {TEST}_CRITICAL_HIGH
```

**Progi krytyczne**: 60% dolnej normy i 150% górnej normy (hardcoded w `data/utils.py:53-54`).

**Augmentacja (tylko train)**:
- **Lab dropout** (15%): losowo pomijamy wynik badania → model uczy się diagnozować przy niepełnych danych
- **Value jitter** (±5%): `val *= uniform(0.95, 1.05)` → symuluje błędy pomiaru / zmienność biologiczną

Parametry w `data/prepare_corpus.py`:
```python
LAB_DROP_PROB   = 0.15
LAB_NOISE_FACTOR = 0.05
```

**Pełna lista parametrów laboratoryjnych**:

| Parametr | Tokeny LOW | Tokeny HIGH | Kliniczne znaczenie |
|---|---|---|---|
| HGB | Q1-Q5, CRITICAL_LOW | Q6-Q10, CRITICAL_HIGH | Niedokrwistość / Czerwienica |
| HCT | Q1-Q5, CRITICAL_LOW | Q6-Q10, CRITICAL_HIGH | Hematokryt |
| PLT | Q1-Q5, CRITICAL_LOW | Q6-Q10, CRITICAL_HIGH | Małopłytkowość / Trombocytoza |
| MCV | Q1-Q5 | Q6-Q10 | Rodzaj niedokrwistości |
| WBC | Q1-Q5 | Q6-Q10, CRITICAL_HIGH | Infekcja / Białaczka |
| CREATININE | — | Q6-Q10, CRITICAL_HIGH | Niewydolność nerek |
| ALT | — | Q6-Q10, CRITICAL_HIGH | Uszkodzenie wątroby |
| AST | — | Q6-Q10, CRITICAL_HIGH | Uszkodzenie wątroby/mięśni |
| UREA | — | Q6-Q10 | Funkcja nerek |

### 2.3 Tokeny triggerów

Tokeny pośrednie — generowane z tokenów laboratoryjnych, wyzwalają pytania adaptacyjne:

| Token | Generowany gdy |
|---|---|
| `TRIGGER_HGB_LOW` | tokeny Q1-Q5 lub CRITICAL_LOW dla HGB |
| `TRIGGER_HGB_HIGH` | tokeny Q6-Q10 lub CRITICAL_HIGH dla HGB |
| `TRIGGER_CREATININE_HIGH` | Q6-Q10 lub CRITICAL_HIGH dla CREATININE |
| itd. | maksymalnie 3 triggery na sekwencję |

Plik: `data/utils.py`, funkcja `extract_triggers(tokens: List[str]) -> List[str]`

### 2.4 Tokeny pytań adaptacyjnych

Pytania są podzielone według grupy wiekowej (`data/questions.json`):

| Grupa | Wiek | Liczba pytań |
|---|---|---|
| `kids` | < 18 | 3 |
| `under_30` | 18–29 | 4 |
| `under_60` | 30–59 | 4 |
| `seniors` | ≥ 60 | 5 |

**Mechanizm (Synthea)**:
1. Wyciągnij triggery z tokenów laboratoryjnych
2. Dla każdej reguły z grupy wiekowej: czy trigger pasuje? → czy gender pasuje?
3. Sprawdź kod SNOMED w historii chorób pacjenta
4. Dodaj `token_yes` lub `token_no`

**Mechanizm (MIMIC)**:
1. Jak wyżej, ale sprawdź kod ICD-9/ICD-10 zamiast SNOMED
2. Mapowanie: `ICD_QUESTION_MAPPING` w `data/prepare_corpus.py`

Przykładowe tokeny pytań:

| Token YES | Token NO | Pytanie kliniczne |
|---|---|---|
| `SYMPTOM_GI_BLEED_YES` | `SYMPTOM_GI_BLEED_NO` | Krew w stolcu? |
| `SYMPTOM_CHEST_PAIN_YES` | `SYMPTOM_CHEST_PAIN_NO` | Ból w klatce piersiowej? |
| `SYMPTOM_EDEMA_YES` | `SYMPTOM_EDEMA_NO` | Obrzęki nóg? |
| `HIST_ALCOHOL_USE_YES` | `HIST_ALCOHOL_USE_NO` | Spożycie alkoholu? |
| `SYMPTOM_DYSURIA_YES` | `SYMPTOM_DYSURIA_NO` | Pieczenie przy oddawaniu moczu? |
| `SYMPTOM_WEIGHT_LOSS_YES` | `SYMPTOM_WEIGHT_LOSS_NO` | Niezamierzona utrata wagi? |

### 2.5 Tokeny docelowe (etykiety)

```
TARGET_POZ          # Podstawowa Opieka Zdrowotna
TARGET_GASTRO       # Gastroenterologia
TARGET_HEMATO       # Hematologia
TARGET_NEFRO        # Nefrologia
TARGET_SOR          # Szpitalny Oddział Ratunkowy
TARGET_CARDIO       # Kardiologia
TARGET_PULMO        # Pulmonologia
TARGET_HEPATO       # Hepatologia
```

Sekwencja z wieloma etykietami: `TARGET_GASTRO,NEFRO` (posortowane alfabetycznie, oddzielone przecinkiem bez spacji).

---

## 3. Etap 0: Przygotowanie corpus

**Plik**: `data/prepare_corpus.py`  
**Wejście**: katalogi Synthea CSV + MIMIC CSV/GZ  
**Wyjście**: `data/train.txt`, `data/val.txt`, `data/mimic_test.txt`

### 3.1 Źródła danych

**Synthea** (syntetyczne dane):
- `patients.csv` → BIRTHDATE, GENDER
- `conditions.csv` → CODE (SNOMED), DESCRIPTION
- `observations.csv` → CODE (LOINC), VALUE

Mapowanie LOINC → nazwa parametru (`LAB_CODES_SYNTHEA`):
```python
"718-7"  → HGB
"777-3"  → PLT
"6690-2" → WBC
"38483-4"→ CREATININE
"1742-6" → ALT
"6299-2" → UREA
# itd.
```

Klasyfikacja do specjalności przez słowa kluczowe SNOMED (`SNOMED_KEYWORDS`) — multi-label (`Set[str]`).

**MIMIC-III/IV** (prawdziwe dane szpitalne):
- `patients.csv` → anchor_age, gender
- `diagnoses_icd.csv` → icd_code (ICD-9 + ICD-10)
- `labevents.csv.gz` → itemid, valuenum (streamowany chunk po chunk — 100M+ wierszy)

Mapowanie itemid → nazwa parametru (`LAB_CODES_MIMIC`):
```python
"51222" → HGB
"51265" → PLT
"51301" → WBC
"50912" → CREATININE
"50861" → ALT
# itd.
```

Klasyfikacja przez prefiksy ICD z `config/icd_mapping.json`. Dla MIMIC: niezmapowane + abnormalne laby → `SOR` (nie silent skip).

### 3.2 Strategia agregacji wartości

| Parametr | Strategia | Uzasadnienie |
|---|---|---|
| HGB, HCT, PLT | `min(values)` | Najgorszy wynik = największe ryzyko |
| WBC, CREATININE, ALT, AST, UREA | `max(values)` | Najwyższy pik = największe ryzyko |
| Synthea | `mean(values)` | Dane populacyjne, mniej krytyczne |

### 3.3 Patient-level split

**Synthea**: 80% train / 20% val (po pacjencie)  
**MIMIC**: 70% train / 10% val / 20% test (po pacjencie)

> **Dlaczego po pacjencie?** Ten sam pacjent może mieć wiele wizyt. Split po wizycie (nie pacjencie) = data leakage — model widziałby inne wizyty tego samego pacjenta podczas treningu i walidacji.

```python
# data/prepare_corpus.py:patient_level_split()
patient_ids = set(pid for _, pid in sequences)
random.shuffle(sorted(patient_ids))
split_idx = int(len(patient_ids) * 0.8)
train_pids = set(patient_ids[:split_idx])
```

### 3.4 Balansowanie klas

Po splicie, na zbiorze treningowym — oversampling mniejszościowych klas do 60% liczebności POZ:

```python
# data/prepare_corpus.py:balance_classes()
target_count = int(max_count * 0.6)  # 60% POZ
for cls, count in class_counts.items():
    if count < target_count:
        extras = random.choices(candidates_for_cls, k=needed)
        balanced.extend(extras)
```

### 3.5 Format wyjściowy

Jeden pacjent = jedna linia w pliku tekstowym:

```
AGE_60 SEX_M HGB_Q5 CREATININE_Q9 PLT_Q7 TRIGGER_HGB_LOW TRIGGER_CREATININE_HIGH SYMPTOM_GI_BLEED_YES SYMPTOM_WEIGHT_LOSS_NO SYMPTOM_CHEST_PAIN_NO TARGET_GASTRO,NEFRO
```

---

## 4. Etap 1: Budowa tokenizera

**Plik**: `model/tokenizer.py`, funkcja `build_tokenizer_from_corpus()`

### 4.1 Dlaczego WordLevel (nie BPE/SentencePiece)?

Standard NLP używa BPE (np. GPT) lub WordPiece (BERT). My używamy **WordLevel** z dwóch powodów:

1. **Nasz "język" nie ma podtokenu** — `HGB_CRITICAL_LOW` to jeden niepodzielny token medyczny, nie składa się z mniejszych sensownych części
2. **Mały słownik** — mamy ~143 unikalne tokeny, BPE nie ma nic do skompresowania

### 4.2 Architektura tokenizera

```
Input:  "AGE_60 SEX_M HGB_Q5 TRIGGER_HGB_LOW SYMPTOM_GI_BLEED_YES TARGET_GASTRO"
         │
         ├── normalizer: Lowercase()
         │   → "age_60 sex_m hgb_q5 trigger_hgb_low symptom_gi_bleed_yes target_gastro"
         │
         ├── pre_tokenizer: Whitespace()
         │   → ["age_60", "sex_m", "hgb_q5", ...]
         │
         ├── WordLevel model: token → integer ID
         │   → [5, 12, 34, 67, 89, 101]
         │
         └── TemplateProcessing: dodaje [CLS] i [SEP]
             → [CLS, 5, 12, 34, 67, 89, 101, SEP]
             → [0,   5, 12, 34, 67, 89, 101,  1]
```

### 4.3 Special tokens

| Token | ID | Użycie |
|---|---|---|
| `[PAD]` | 0 | Padding do długości 128 |
| `[UNK]` | 1 | Nieznany token (nie powinien wystąpić) |
| `[CLS]` | 2 | Start sekwencji — jego reprezentacja = embedding całego zdania |
| `[SEP]` | 3 | Koniec sekwencji |
| `[MASK]` | 4 | Maskowany token w MLM |

### 4.4 Zapis i ładowanie

```bash
# Tokenizer budowany automatycznie przez pretrain_mlm.py
# Zapis: checkpoints/mlm/tokenizer/
#   tokenizer.json         ← mapa token→id
#   tokenizer_config.json  ← konfiguracja
#   special_tokens_map.json

# Ładowanie:
from model.tokenizer import load_tokenizer
tokenizer = load_tokenizer(Path("checkpoints/mlm/tokenizer"))
```

---

## 5. Etap 2: MLM Pretraining

**Plik**: `model/pretrain_mlm.py`

### 5.1 Czym jest MLM?

Masked Language Model uczy model "rozumieć" kontekst bez nadzoru (bez etykiet klas). Procedura:

```
Input:   AGE_60  SEX_M  HGB_Q5   CREATININE_Q9  SYMPTOM_GI_BLEED_YES
          │        │      │            │                │
         OK       OK    [MASK]        OK             [MASK]
          │        │      │            │                │
Output:  AGE_60  SEX_M  HGB_Q5  CREATININE_Q9  SYMPTOM_GI_BLEED_YES
                         ▲                            ▲
                    Przewidziany                Przewidziany
```

15% tokenów jest losowo maskowanych. Model musi odgadnąć oryginał na podstawie kontekstu.

**Co model się uczy?**
- `HGB_Q5` + `AGE_60` + `SEX_M` → HEMATO/GASTRO pattern
- `TRIGGER_CREATININE_HIGH` → prawdopodobnie `SYMPTOM_EDEMA_YES` w pobliżu
- Korelacje między parametrami laboratoryjnymi a objawami

### 5.2 Architektura modelu (z paper)

| Parametr | Wartość | Uwaga |
|---|---|---|
| Liczba warstw | 6 | Encoder-only (jak BERT-small) |
| Hidden size | 256 | (BERT-base ma 768) |
| Attention heads | 8 | hidden/heads = 32 (musi być całkowite) |
| FFN size | 1024 | = 4 × hidden_size |
| Max sequence length | 128 | Wystarczy dla ~20 tokenów medycznych |
| Vocab size | ~143 | WordLevel z naszego corpus |
| Dropout | 0.1 | Wszędzie |
| Activation | GELU | Standard BERT |

Plik: `model/bert_model.py`, funkcja `get_bert_config(vocab_size)`

Całkowita liczba parametrów: ~4.2M (BERT-base ma 110M — nasz jest 26× mniejszy, bo słownik i wymiary są małe).

### 5.3 Hiperparametry pretrainingu

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| Learning rate | 1e-4 | Wyższe niż fine-tune (model trenuje od zera) |
| Batch size | 64 | Balans między stabilnością a szybkością |
| Warmup steps | 500 | ~5% kroków treningu, stabilizacja na początku |
| Weight decay | 0.01 | L2 regularyzacja (nie na bias i LayerNorm) |
| Max grad norm | 1.0 | Gradient clipping, zapobiega eksplozji gradientów |
| MLM probability | 0.15 | Standard BERT (15% tokenów maskowanych) |
| Epochs | 15 | Z early stopping (patience=3) |
| Corpus split | 90/10 | train/val po shuffle (seed=42) |

### 5.4 Co się dzieje krok po kroku

```python
# 1. Zbuduj tokenizer z całego corpus
tokenizer = build_tokenizer_from_corpus(corpus_path, vocab_size=143)

# 2. Załaduj corpus, podziel 90/10
all_lines = shuffle(corpus_lines, seed=42)
train_lines = all_lines[:90%]
val_lines   = all_lines[10%:]

# 3. DataCollatorForLanguageModeling maskuje 15% tokenów w locie
collator = DataCollatorForLanguageModeling(tokenizer, mlm_probability=0.15)

# 4. Trening: model.forward(masked_input) → logits → CrossEntropyLoss na zamaskowanych
# 5. Early stopping gdy val_loss nie spada przez 3 epoki
# 6. Zapisz model + tokenizer
model.save_pretrained("checkpoints/mlm/")
tokenizer.save_pretrained("checkpoints/mlm/tokenizer/")
```

### 5.5 Oczekiwane wyniki MLM

| Metryka | Wartość docelowa | Interpretacja |
|---|---|---|
| Train loss | < 0.5 | Model dobrze przewiduje maskowane tokeny |
| Val loss | < 0.8 | Brak przeuczenia |
| Perplexity | < 2.0 | exp(0.7) ≈ 2.0 — małe vocab = łatwe zadanie |

> **Uwaga**: Perplexity blisko 1.0 to sygnał przeuczenia — vocab jest za mały i model zapamiętuje. Val loss wyraźnie wyższy niż train loss — za duże dropout lub za mało danych.

---

## 6. Etap 3: Fine-tuning (klasyfikacja)

**Plik**: `model/finetune_multilabel.py`

### 6.1 Architektura klasyfikatora

```
Sekwencja → [CLS] token embedding (dim=256)
                     │
                  Dropout(0.1)
                     │
              Linear(256 → 8)  ← 8 klas
                     │
                  (logits)
                     │
                  Sigmoid         ← nie Softmax! (multi-label)
                     │
              8 prawdopodobieństw ∈ (0, 1)
```

**Dlaczego Sigmoid a nie Softmax?**
- Softmax: klasy wzajemnie wykluczające → suma = 1
- Sigmoid: każda klasa niezależna → możliwe GASTRO=0.8 i NEFRO=0.7 jednocześnie
- Pacjent może wymagać wielu specjalistów → multi-label

### 6.2 Funkcja straty — Cost-Sensitive Focal Loss

**Plik**: `model/losses.py`, klasa `FocalBCELoss`

```
Loss = mean[ (1 - p_t)^γ · BCE(logit, y) · w_c ]

gdzie:
  p_t = σ(logit)·y + (1-σ(logit))·(1-y)   ← prawdopodobieństwo "prawidłowej" klasy
  γ = 2.0 (focal exponent)
  w_c = koszt kliniczny klasy c
  BCE = Binary Cross-Entropy
```

**Trzy składniki**:

1. **BCE** — standardowa strata binarna dla każdej klasy osobno
2. **`(1-p_t)^γ`** — **focal weight**: przykłady dobrze sklasyfikowane (p_t ≈ 1) dostają wagę ≈ 0; trudne przykłady (p_t ≈ 0.5) dostają wagę ≈ 0.25. Γ=2 skupia model na trudnych przypadkach.
3. **`w_c`** — **cost weight**: pominięcie SOR (nagły) jest 10× droższe niż POZ

**Macierz kosztów**:

| Klasa | Koszt | Uzasadnienie |
|---|---|---|
| SOR | **10** | Pominięcie nagłego = zagrożenie życia |
| NEFRO | 7 | Opóźnienie nefrologa → dializa |
| HEMATO | 7 | Opóźnienie hematologa → powikłania |
| CARDIO | 5 | Opóźnienie kardiologa → zawał |
| PULMO | 5 | Opóźnienie pulmonologa → niewydolność |
| GASTRO | 5 | Opóźnienie gastrologa → krwawienie |
| HEPATO | 4 | Opóźnienie hepatologa → marskość |
| POZ | 1 | Fałszywy alarm = tylko zbędna wizyta |

### 6.3 Progi decyzyjne (per-class)

Progi **nie są** dobierane ręcznie — po treningu `evaluate.py` kalibruje je automatycznie z krzywej ROC (patrz Etap 4). Wartości domyślne (przed kalibracją):

| Klasa | Próg domyślny | Logika |
|---|---|---|
| SOR | 0.35 | Minimalizuj FNR (miss) |
| Specjaliści | 0.45 | Balans |
| POZ | 0.55 | Ostrożnie z "nie ma problemu" |

### 6.4 Hiperparametry fine-tuningu

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| Learning rate | 2e-5 | 5× mniejsze niż MLM (model jest wstępnie wytrenowany) |
| Batch size | 32 | |
| Warmup steps | 300 | ~10% kroków fine-tuningu |
| Weight decay | 0.01 | |
| Focal gamma | 2.0 | Standardowy Focal Loss |
| Epochs | 5 | Małe — overfitting przy wstępnym treningu |
| Early stopping | patience=2 | Na `macro_roc_auc` (nie na loss) |

> **Dlaczego early stopping na `macro_roc_auc` a nie `eval_loss`?**  
> Minimalizacja cost-weighted loss ≠ optymalizacja AUC klinicznego. Model może mieć niski loss ale złe AUC dla rzadkich klas. `macro_roc_auc` bezpośrednio mierzy zdolność rozróżniania klas niezależnie od progu.

### 6.5 Metryki treningowe

Po każdej epoce `compute_metrics()` oblicza:

- `roc_auc_{CLASS}` — AUC per klasa (niezależne od progu)
- `f1_{CLASS}` — F1 z per-class threshold
- `precision_{CLASS}`, `recall_{CLASS}` — per klasa
- `macro_roc_auc` — średnia AUC po wszystkich klasach (metryka early stopping)
- `ece` — Expected Calibration Error (target < 0.012)

---

## 7. Etap 4: Ewaluacja i kalibracja

**Plik**: `model/evaluate.py`

### 7.1 Temperature Scaling

Po fine-tuningu prawdopodobieństwa modelu mogą być źle skalibrowane (zbyt pewny lub zbyt niepewny). Temperature scaling to prosta korekta jednym parametrem T:

```
p_calibrated = sigmoid(logit / T)
```

- T > 1: model mniej pewny (wygładza prawdopodobieństwa)
- T < 1: model bardziej pewny
- T = 1: bez zmiany

**Implementacja**: LBFGS minimalizuje `BCE(logit/T, labels)` na zbiorze walidacyjnym przy zamrożonych wagach modelu. Tylko `T` jest optymalizowane.

```python
# model/evaluate.py:ModelWithTemperature.set_temperature()
optimizer = torch.optim.LBFGS([self.temperature], lr=0.01, max_iter=50)
def eval_():
    loss = BCEWithLogitsLoss(all_logits / self.temperature, all_labels)
    loss.backward()
    return loss
optimizer.step(eval_)
```

**Cel**: ECE (Expected Calibration Error) < 0.012 (z paper).

### 7.2 Kalibracja progów z krzywej ROC

**Funkcja**: `calibrate_thresholds(probs, labels, cost_weights, output_path)`

Dla każdej klasy z osobna:
1. Oblicz krzywą ROC: `fpr_arr, tpr_arr, thr_arr = roc_curve(labels, probs)`
2. Dla każdego progu `t` oblicz koszt kliniczny:
   ```
   fnr(t) = 1 - tpr(t)
   cost(t) = w_c · fnr(t) + fpr(t)
   ```
3. Wybierz `t` minimalizujące `cost(t)`

**Intuicja**:
- Wysoki koszt (`w_c` = 10 dla SOR) → mocno karane FNR → optimal threshold nisko (łap wszystkich)
- Niski koszt (`w_c` = 1 dla POZ) → FNR i FPR traktowane równo → standardowy punkt operacyjny

Wynik zapisywany do `checkpoints/finetune/class_thresholds.json`:
```json
{
  "SOR":    0.287,
  "NEFRO":  0.412,
  "HEMATO": 0.389,
  "CARDIO": 0.445,
  "PULMO":  0.433,
  "GASTRO": 0.401,
  "HEPATO": 0.463,
  "POZ":    0.571
}
```

### 7.3 Multi-label safety prediction

```python
# model/evaluate.py:safety_predict()
for class_idx, class_name in REVERSE_LABEL_MAP.items():
    thr = thresholds[class_name]
    if prob[class_idx] > thr:
        flags.append(class_name)

# SOR ma pierwszeństwo — jeśli SOR, usuń innych specjalistów
if "SOR" in flags:
    flags = ["SOR"]
elif not flags:
    flags = ["POZ"]
```

### 7.4 ECE — Expected Calibration Error

Mierzy ile model się "myli" w swojej pewności. Idea: jeśli model mówi "70% szans na HEMATO", to wśród takich przypadków faktycznie ~70% powinno mieć HEMATO.

```
ECE = Σ_bins (|avg_confidence_bin - accuracy_bin|) × (samples_in_bin / total)
```

Target z paper: ECE < 0.012 per klasa.

---

## 8. Etap 5: API — wdrożenie

**Plik**: `api/main.py`

### 8.1 Ładowanie przy starcie

```python
@app.on_event("startup")
async def startup():
    LAB_NORMS     = load_lab_norms("config/lab_norms.json")
    QUESTIONS_BANK = load_questions_bank("data/questions.json")

def load_model(model_path):
    TOKENIZER = load_tokenizer(model_path / "tokenizer")
    MODEL     = BertForMultiLabelClassification.from_pretrained(model_path)
    # Ładuj kalibrowane progi jeśli dostępne:
    if (model_path / "class_thresholds.json").exists():
        CLASS_THRESHOLDS.update(json.load(...))
```

### 8.2 Endpoint POST /predict

```
Wejście JSON:
  {age: 65, sex: "M", hgb: 9.5, creatinine: 2.1, alt: 45}

Przetwarzanie:
  1. Kwantyzacja: get_lab_token_v2() per parametr
  2. extract_triggers() → TRIGGER_HGB_LOW, TRIGGER_CREATININE_HIGH
  3. Sekwencja: "AGE_60 SEX_M HGB_Q5 CREATININE_Q9 ALT_Q6 TRIGGER_HGB_LOW ..."
  4. tokenizer(sequence) → input_ids [1, 128]
  5. model(input_ids) → logits [1, 8]
  6. sigmoid(logits) → probs [1, 8]
  7. Per-class threshold → flags = ["NEFRO", "HEMATO"]

Wyjście JSON:
  {flags: ["NEFRO", "HEMATO"],
   probabilities: {POZ: 0.12, GASTRO: 0.21, HEMATO: 0.67, NEFRO: 0.78, ...},
   attention: {hgb_q5: 0.34, creatinine_q9: 0.41, ...},
   tokens: ["AGE_60", "SEX_M", ...]}
```

### 8.3 Endpoint GET /questions/{param}?age=65

Zwraca pytania adaptacyjne dla danego parametru i grupy wiekowej:
```json
{"questions": [
  {"trigger": "HGB_LOW", "intent": "GI_BLEED_CHECK",
   "text": "Czy zauważyłeś czarny, smolisty stolec?",
   "token_yes": "SYMPTOM_GI_BLEED_YES",
   "token_no": "SYMPTOM_GI_BLEED_NO",
   "age_group": "seniors"}
]}
```

---

## 9. Architektura BERT — szczegóły

### 9.1 Porównanie z papierem

| Parametr | Paper | Implementacja | Plik |
|---|---|---|---|
| Layers | 6 | 6 | `bert_model.py:24` |
| Hidden size | 256 | 256 | `bert_model.py:25` |
| Attention heads | 8 | 8 | `bert_model.py:26` |
| FFN size | 1024 | 1024 | `bert_model.py:27` |
| Vocab size | ~140 | ~143 | `bert_model.py:22` |
| Max seq len | 128 | 128 | `bert_model.py:31` |
| Dropout | 0.1 | 0.1 | `bert_model.py:35-36` |

### 9.2 Jak działa CLS token dla klasyfikacji

```
Input: [CLS] AGE_60 SEX_M HGB_Q5 ... [SEP] [PAD] [PAD]
         │      │      │      │
         └──────┴──────┴──────┴──── Self-Attention (6 layers)
                                         │
         CLS reprezentuje "zdanie"  ←────┘ (pooling through attention)
                │
            Dropout
                │
            Linear(256→8)
                │
            Logits [8]
                │
            Sigmoid
                │
         Probabilities [8]
```

**Dlaczego CLS (nie mean pooling)?** Ethos notebooks i BERT paper używają CLS. Mean pooling mógłby też działać, ale CLS jest trenowany end-to-end do reprezentowania całej sekwencji.

### 9.3 Attention weights dla explainability

```python
# api/main.py
outputs = model(input_ids, attention_mask, output_attentions=True)
last_layer_attention = outputs.attentions[-1][0]   # ostatnia warstwa
cls_attention = last_layer_attention[0].mean(dim=0)  # head avg, CLS row
```

Wynik: per-token wagi wskazujące które badania najbardziej wpłynęły na decyzję. Np. `creatinine_q9: 0.41` → nerki były kluczowe dla diagnozy NEFRO.

---

## 10. Jak testować każdy etap

### Etap 0: Weryfikacja corpus

```bash
# Uruchomienie (pełne dane)
python data/prepare_corpus.py \
  --synthea-dir data/synthea_new/ \
  --mimic-dir data/mimic/ \
  --output-train data/train.txt \
  --output-val data/val.txt \
  --output-mimic-test data/mimic_test.txt

# Weryfikacja obecności tokenów symptomów
grep -c "SYMPTOM_" data/train.txt
# oczekiwane: > 0 (dziesiątki tysięcy)

grep -c "SYMPTOM_" data/val.txt
# oczekiwane: > 0

# Sprawdź rozkład klas
grep -oP "TARGET_\K[A-Z,]+" data/train.txt | sort | uniq -c | sort -rn

# Sprawdź przykładową sekwencję
head -5 data/train.txt

# Sprawdź augmentację — każda linia train powinna mieć ~6-8 tokenów lab
awk '{print NF}' data/train.txt | sort -n | uniq -c | head -20
```

**Czego szukać**:
- Tokeny `SYMPTOM_*` i `HIST_*` → pytania działają
- Brak tokenów `Q-1`, `Q-9` → bug kwantyzacji naprawiony
- Klasa SOR powinna mieć ~10-15% sekwencji (nie 0%)
- Długości sekwencji: 5–20 tokenów (przed paddingiem)

### Etap 1: Weryfikacja tokenizera

```bash
# Tokenizer buduje się automatycznie podczas pretrain_mlm.py
# Można też zbudować osobno:
python -c "
from model.tokenizer import build_tokenizer_from_corpus
from pathlib import Path
tok = build_tokenizer_from_corpus(Path('data/train.txt'), vocab_size=256)
print('Vocab size:', len(tok.get_vocab()))
print('Sample tokens:', list(tok.get_vocab().keys())[:20])
# Sprawdź krytyczne tokeny
for t in ['hgb_q5', 'symptom_gi_bleed_yes', 'target_sor', 'trigger_hgb_low']:
    id_ = tok.convert_tokens_to_ids(t)
    print(f'  {t} → id={id_} (UNK=1, OK={id_!=1})')
"
```

**Czego szukać**:
- Rozmiar vocab: 130–250 (zależy od corpus)
- Krytyczne tokeny NIE powinny być UNK (id=1)
- Tokeny medyczne poprawnie tokenizowane jako całość (nie split)

### Etap 2: MLM Pretraining

```bash
# Uruchomienie
python model/pretrain_mlm.py \
  --corpus data/train.txt \
  --output checkpoints/mlm/ \
  --epochs 15 \
  --batch-size 64 \
  --lr 1e-4 \
  --vocab-size 256

# Quick test (kilka sekund)
python model/pretrain_mlm.py \
  --corpus data/train.txt \
  --output checkpoints/mlm_test/ \
  --epochs 2 \
  --max-samples 1000

# Sprawdź logi po treningu
cat checkpoints/mlm/logs/...
```

**Czego szukać**:
- `train_loss` powinno spadać każdą epokę
- `eval_loss` powinno być bliskie `train_loss` (brak overfitting)
- Early stopping po ~10-12 epokach (przy dobrych danych)
- Brak `nan` lub `inf` w loss

### Etap 3: Fine-tuning

```bash
# Uruchomienie
python model/finetune_multilabel.py \
  --pretrained checkpoints/mlm/ \
  --train-corpus data/train.txt \
  --val-corpus data/val.txt \
  --output checkpoints/finetune/ \
  --focal-gamma 2.0

# Oczekiwane logi per epoka:
# eval_roc_auc_SOR   = 0.95-1.00
# eval_roc_auc_NEFRO = 0.90-0.95
# eval_macro_roc_auc = 0.88-0.95
# eval_ece           = 0.008-0.015
```

**Czego szukać**:
- `macro_roc_auc` rośnie z epoką
- AUC dla SOR > 0.95 (paper: 1.00)
- ECE < 0.015 (paper target: 0.012)
- Recall dla SOR > 0.90 (ważniejszy niż precision)

### Etap 4: Ewaluacja i kalibracja

```bash
# Uruchomienie na zbiorze testowym MIMIC
python model/evaluate.py \
  --model checkpoints/finetune/ \
  --corpus data/mimic_test.txt \
  --device cpu

# Sprawdź wyjście:
# - Temperature: powinna być blisko 1.0 (dobrze skalibrowany model)
# - ECE po kalibracji < ECE przed kalibracją
# - class_thresholds.json stworzony

cat checkpoints/finetune/class_thresholds.json
```

### Etap 5: Testowanie API

```bash
# Uruchom serwer
uvicorn api.main:app --reload --port 8000

# Test predykcji — pacjent z niskim HGB i wysokim kreatininą
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age": 65, "sex": "M", "hgb": 9.5, "creatinine": 2.1, "wbc": 12.0}'

# Oczekiwane: flags zawiera NEFRO i/lub HEMATO

# Test pytań adaptacyjnych
curl "http://localhost:8000/questions/hgb?age=65"

# Test health
curl http://localhost:8000/health
```

---

## 11. Typowe błędy i diagnostyka

### Problem: `Q-5` lub ujemne kwantyle w corpus

**Przyczyna**: Stary bug w `data/utils.py` — `min(q,5)` nie chroniło przed ujemnymi.  
**Status**: Naprawione — `max(1, min(5, q))`.  
**Weryfikacja**: `grep "Q-" data/train.txt | wc -l` → powinno dać 0.

---

### Problem: Brak tokenów `SYMPTOM_*` w corpus

**Przyczyna 1**: `load_questions_bank()` zwracała złą strukturę.  
**Status**: Naprawione — funkcja zwraca `Dict[age_group, List[Dict]]`.

**Przyczyna 2**: `questions_db` nie był przekazywany do `preprocess_synthea`.  
**Status**: Naprawione — `questions_db=questions_db` w wywołaniu.

**Diagnostyka**:
```bash
python -c "
from data.utils import load_questions_bank
from pathlib import Path
db = load_questions_bank(Path('data/questions.json'))
print(db.keys())  # powinno: dict_keys(['kids', 'under_30', 'under_60', 'seniors'])
"
```

---

### Problem: `eval_dataset == train_dataset` w MLM

**Przyczyna**: Stary kod przekazywał ten sam dataset do train i eval.  
**Status**: Naprawione — shuffle + 90/10 split przed tworzeniem Dataset.  
**Weryfikacja**: W logach MLM powinno być "Split: X train / Y val".

---

### Problem: `macro_roc_auc` nie rośnie podczas fine-tuningu

**Możliwe przyczyny**:
1. Zbyt mała różnorodność danych — sprawdź rozkład klas w corpus
2. Za duże klasy dominujące — sprawdź balansowanie (60% POZ target)
3. Zbyt mały learning rate — spróbuj 3e-5
4. MLM nie był dobrze wytrenowany — sprawdź `val_loss` < 0.8

---

### Problem: SOR nigdy nie jest wykrywany

**Możliwe przyczyny**:
1. Klasa SOR ma za mało próbek → sprawdź `CLASS_LIMITS` (domyślnie 40k)
2. Próg za wysoki — po `evaluate.py` powinien spaść do ~0.3
3. Dane MIMIC nie mają oznaczeń SOR → sprawdź `icd_mapping.json` dla SOR

---

### Problem: Temperature scaling nie zmienia ECE

**Diagnostyka**: Sprawdź czy `temperature` jest uczony przez LBFGS:
```bash
python -c "
# Sprawdź czy temperature_scaling.json istnieje po evaluate.py
ls -la checkpoints/finetune/class_thresholds.json
cat checkpoints/finetune/class_thresholds.json
"
```

Jeśli T ≈ 1.0 po optymalizacji — model jest już dobrze skalibrowany (to dobry wynik).

---

*Dokumentacja wygenerowana dla BloodAI v1.0 — Hackathon "Built with Opus 4.7", 2026-04-26*
