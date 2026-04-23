# Metodologiczna Weryfikacja Artykułu
## "Intelligent Multi-Label Triage for Hematological Comorbidities using BERT"
### Banasik & Pater, 2026

---

## STRESZCZENIE WYKONAWCZE

Artykuł prezentuje solidnie zaprojektowaną metodologię multi-label triażu klinicznego z użyciem BERT. **Siła**: rzetelna walidacja na poziomie pacjenta, jawna obsługa kosztu klinicznego, hybrydowy corpus, niskie ECE. **Słabości**: ryzyko overfittingu na Synthea, brak walidacji prospektywnej,rak modelowania temporal. Metodologia jest **w większości prawidłowa** dla hackathonu akademickiego, ale ma jasno zdefiniowane ograniczenia.

---

## 1. METODOLOGIA TRENINGU MODELU

### 1.1 MLM Pre-training

| Aspekt | Status | Uzasadnienie |
|--------|--------|--------------|
| **Prawidłowość MLM** | ✓ Poprawne | Standardowe podejście; 15% maskowania jest konwencją. Maskowanie, random token replacement (10%), unchanged (10%) zachowuje balans. |
| **In-domain adaptation** | ✓ Poprawne | Pre-training na tym samym corpus (Synthea + MIMIC) przed fine-tuning zapewnia dostosowanie do domeny medycznej i specific vocabulary (~140 tokenów). |
| **Learning rate MLM** | ✓ Poprawne | lr = 10⁻⁴ dla pre-trainingu, następnie lr = 2×10⁻⁵ dla fine-tuningu (10x niżej) – standardowe schowanie. |
| **Liczba epok (15)** | ⚠️ Bez uzasadnienia | Brak badania konwergencji. Nie ma validation loss curve. Ryzyko: zatrzymanie zbyt wcześnie lub zbyt późno. |

**Wnioski**: MLM pre-training jest prawidłowe, ale artykuł nie raportu eksperymentów ablacyjnych: co daje pre-training vs. fine-tuning from scratch?

### 1.2 Architektura BERT

| Element | Wartość | Ocena |
|---------|---------|-------|
| **Liczba warstw** | 6 | ✓ Uzasadnione dla małego corpus (260k samples) – większa by mogła overfit |
| **Hidden dimension** | 256 | ✓ Rozsądne dla ~140 tokenów; zmniejsza parametry |
| **Attention heads** | 8 | ✓ Prawidłowe (256 / 8 = 32 dim per head) |
| **FFN intermediate** | 1024 | ✓ Typowo 4x hidden size (256 × 4 = 1024) |
| **Max sequence length** | 128 tokenów | ⚠️ Potencjalna konsekwencja: obcinanie długich sekwencji |

**Ocena**: Architektura jest **celowo zmniejszona** (mniejsza niż BERT-base), co jest rozsądne dla domeny medycznej, ale brak justyfikacji empirycznej (np. comparison z 12-layer BERT).

### 1.3 Multi-label Fine-tuning z BCEWithLogitsLoss

| Aspekt | Status | Szczegóły |
|--------|--------|----------|
| **BCE na logits** | ✓ Poprawne | Właściwy wybór dla multi-label; niezależna sigmoid per class. Unika softmax constraint. |
| **Linear → Sigmoid** | ✓ Poprawne | 8 independent probabilities ∈ [0,1]. Pozwala na wieloetykietowość. |
| **Brak softmax** | ✓ Poprawne | Krytycznie ważne: softmax byłby błędem (wymuszałby P(class_i) + P(class_j) = 1). |
| **Per-class thresholds** | ✓ Dobra praktyka | Tuning na validation set; niższy threshold dla SOR (priorytet czułości). |

**Wnioski**: Fine-tuning dla multi-label jest **metodologicznie prawidłowy**.

### 1.4 Cost-Sensitive Focal Loss

| Element | Ocena | Zastrzeżenia |
|---------|-------|--------------|
| **Clinical Cost Matrix C_ij** | ✓ Pomysł słuszny | Przypisanie wyższego kosztu FN dla SOR (8-10) niż FP jest kliniczne uzasadnione. |
| **Focal Loss (γ > 0)** | ✓ Właściwe | Downweighting easy examples, upweighting hard cases – dobrze dla klasy rare (SOR). |
| **Kombinacja BCE + focal** | ⚠️ Niejasna | **PROBLEM**: Artykuł **nie ujawnia równania** ani wartości γ, ani konkretne wagi. Brak ablacji: co daje cost vs. focal? |
| **Reproductibility** | ❌ Niedostateczna | Nie ma kodu loss function. Nie wiadomo, jak dokładnie kombinuje się BCE z focal. |

**Krytyka**: Cost-sensitive focal loss jest **konceptualnie słuszna**, ale **niedostatecznie dokumentowana** dla reproducibility.

---

## 2. PRZYGOTOWANIE DANYCH

### 2.1 Patient-level Split (80/20)

| Kryterium | Status | Analiza |
|-----------|--------|--------|
| **Brak leakage** | ✓ Doskonałe | Każdy pacjent (subject_id) całkowicie w train lub val – eliminuje pacjenta z train i val (leak). |
| **Stratified sampling** | ✓ Wspomniane | "Approximately respect multi-label distribution" – brak szczegółów, ale intencja jest dobra. |
| **Oddzielność MIMIC/Synthea** | ❓ Pytanie | Czy split jest stratified po źródle danych? Czy val ma mix Synthea + MIMIC? |
| **Reprezentatywność** | ✓ Raczej tak | "Each class appears in both train and val" – zapewnia, że val metrics odzwierciedlają unseen patients. |

**Wniosek**: Patient-level split jest **prawidłowy i eliminuje leakage**. Brak jednak szczegółów na temat stratyfikacji po klasach.

### 2.2 Hybrydowy Corpus (Synthea + MIMIC)

| Źródło | Zaleta | Wada | Ryzyko |
|--------|--------|------|--------|
| **Synthea** | Chronic trajectories, well-labeled, large variety, reproducible | Rule-based patterns (regularne, sztuczne) | Overfitting do generator – metryki optimistycznie skłonione |
| **MIMIC-III/IV** | Real ICU data, acute presentations, narrative notes | Biased toward ICU (nie primary care), US-centric | Single-center bias, limited generalizability |
| **Hybrydowy mix** | Kompromis – widzi chronic + acute | – | Synthea dominuje (?) – jak jest ratio? |

**Pytania nieodpowiedziane**:
- Ile Synthea vs. MIMIC? Tabela I mówi 260k training + 65k val, ale brak breakdown.
- Czy Synthea dominuje? Jeśli tak, czy test na MIMIC-only hold-out byłby lepszy?
- Czy model nie „uczy się" artefaktów Synthea (np. zbyt regular patterns)?

**Rekomendacja**: Autorzy wspominają "Future work: report separate metrics on MIMIC-only hold-out" – to byłoby **kluczowe dla wiarygodności**.

### 2.3 Tokenizacja Lab Parametrów (Quintiles, Critical Bands)

| Strategie | Ocena | Uwagi |
|-----------|-------|-------|
| **Quintile binning (Q1-Q5)** | ✓ Rozumna | Kwantyzuje ciągłe wartości w dyskretne tokeny; model uczy się non-linear boundaries. |
| **Critical bands** (np. HGB_CRITICAL_LOW) | ✓ Kliniczne sensowne | Dodatkowo encode'uje extreme values, ważne dla SOR. |
| **Usunięcie raw numbers** | ✓ Interpretowalne | Zamiast 7.5 g/dL → HGB_Q4; czyni sekwencję słownikiem klinicznym. |
| **Composite tokens** | ✓ Engineering rozsądny | Np. COMPOSITE_ANEMIA_INDICATOR – kombinuje wiele sygnałów. |
| **Problem: Quintiles per age/sex** | ⚠️ Wzmiankami ale niejasne | Artykuł mówi o age/sex-dependent reference ranges w lab_norms.json, ale nie jasne, czy quintiles są stratified? |

**Krytyka**: Tokenizacja jest **metodologicznie słuszna**, ale brakuje szczegółów na temat kalibracji quintiles (czy ustalone na training set? czy na literatura medyczną?).

### 2.4 Balansowanie Klas (Imbalanced)

| Klasa | Częstość | Obsługa |
|-------|----------|---------|
| **Haematology, Nephrology** | Częste | Cost-sensitive focal loss, per-class threshold |
| **SOR (Emergency)** | Rare | Niższy threshold, wyższy cost FN (8-10) |
| **Cardiology, Pulmonology** | Pośrednie | Standard weighting |

**Ocena**: 
- ✓ Cost matrix explicit – SOR ma cost 8-10 dla FN vs. POZ
- ⚠️ Brak informacji na temat ratio klasy (np. SOR jest X% positive). Bez tego nie można ocenić, czy undersampling/oversampling był użyty.
- ⚠️ Artykuł wspomina "optional data augmentation for rare class pairs" ale nie podaje szczegółów.

**Rekomendacja**: Tabela z distribution klas byłaby kluczowa (np. % samples z każdą etykietą).

---

## 3. METRYKI EWALUACJI

### 3.1 ROC AUC, AUPRC, ECE

| Metrika | Właściwa dla multi-label? | Ocena |
|---------|--------------------------|-------|
| **ROC AUC (one-vs-rest)** | ✓ Tak | Standard dla multi-label; osobna krzywa per klasa. Wyniki: SOR=1.00, Haem=0.94, Neph=0.95 – doskonałe. |
| **AUPRC** | ✓ Tak | Bardziej informacyjna dla imbalanced klas niż ROC. High AUPRC dla SOR, Haem. |
| **ECE** | ✓ Tak | Istotna dla clinical decision support. Model's ECE: 0.007-0.012 << 0.05 – bardzo dobrze. |
| **Subset Accuracy** | ⚠️ Zmniejsza | Multi-label subset accuracy (dokładne match wszystkich 8 labels) typowo niskie – autorzy słusznie go pomijają. |
| **Hamming Loss** | ✓ Wspominane | "Fraction of label positions wrong" – proper multi-label metric. |

**Wniosek**: Metryki są **prawidłowo wybrane** dla multi-label.

### 3.2 Confusion Matrices per-class

| Klasa | TP | FP | FN | TN | Interpretacja |
|-------|-----|-----|-----|------|---------------|
| **SOR** | 21811 | 0 | 0 | 7532 | Perfect (!)  – Sensitivity=1.0, Specificity=1.0 |
| **Haematology** | 25214 | 1872 | 2044 | 4953 | Good diagonal dominance |
| **Nephrology** | 15310 | 1804 | 2258 | 9971 | Good, ale F1=0.883 < 0.913 (Haem) |

**Ocena**: 
- ✓ SOR confusion matrix jest doskonały (0 FN, 0 FP) – **ale to podejrzane**. Prawdopodobnie artefakt: validation set jest mały lub SOR jest trivial do oddzielenia od reszty (wysokie creatinine, białaczka).
- ✓ Haem, Neph mają realistyczne FP/FN.

**Zastrzeżenie**: Perfect SOR performance (1.00 ROC AUC, 0 errors) sugeruje, że klasa jest **zbyt łatwa** lub validation set jest **non-representative**.

### 3.3 Patient-level Validation

| Aspekt | Status | Uzasadnienie |
|--------|--------|--------------|
| **Patient-level separation** | ✓ Wykonane | Split na subject_id – unika leakage. |
| **Metrics reflect generalization** | ✓ Interpretowalne | ROC AUC, ECE na unseen pacjentach – relevant dla deployment. |
| **Hybrid corpus validation** | ⚠️ Częściowe | Validation zawiera Synthea + MIMIC, ale brak separate metrics dla każdego. |

**Rekomendacja**: Autorzy wspominają "Future work: prospective validation in primary care" – to byłoby **niezbędne** dla real-world deployment.

---

## 4. POTENCJALNE SŁABE PUNKTY I ULEPSZENIA

### 4.1 Overfitting do Synthea (Syntetyczne Dane)

| Problem | Ryzyk | Mitygacja | Status |
|---------|-------|-----------|--------|
| **Synthea rule-based** | ✓ Wysokie | Hybrid corpus zmniejsza ryzyko | ⚠️ Niedostateczne |
| **Metryki na Synthea+MIMIC val** | ✓ Optymistycznie skłonione | Separate MIMIC-only hold-out test | ❌ Brak |
| **Nie ma prospective validation** | ✓ Wysokie | Wdrożenie real-world | ❌ Zaplanowane na future |

**Rekomendacja**: 
```
Przed deployment: ocenić model na:
1. MIMIC-only test set (no Synthea)
2. External primary care cohort (jeśli dostępne)
```

### 4.2 Brak Temporal Modeling

| Aspekt | Opis | Wpływ |
|--------|------|-------|
| **Input**: one encounter only | Model widzi jeden snapshot labów, nie longitudinal trend | ⚠️ Średnie |
| **Trend significance** | Haemoglobin 6.5 → 7.0 (wzrastające) inny niż 7.0 → 6.5 (spadające) | Potencjal miss kliniczny |
| **Multi-encounter validation** | Nie poruszono | Brak test scenariusza: "pacjent z 3 visits, jak się zmienia triász?" |

**Rekomendacja**: 
- Dodać LSTM/RNN head dla temporal sequences
- Albo minimum: include "trend tokens" (e.g., HGB_RISING, HGB_FALLING)

### 4.3 Hyperparameter Selection

| Parametr | Wartość | Uzasadnienie | Status |
|----------|---------|--------------|--------|
| **Learning rates** | MLM: 10⁻⁴, FT: 2×10⁻⁵ | Standardowe | ✓ OK |
| **Batch sizes** | 64 (MLM), 32 train / 64 val (FT) | Rozsądne dla 260k samples | ✓ OK |
| **Max epochs MLM** | 15 | Brak uzasadnienia | ⚠️ Arbitralne |
| **Max epochs FT** | 5 | Brak uzasadnienia | ⚠️ Arbitralne |
| **γ (focal loss)** | ?? | **Nie podano!** | ❌ Brak |
| **Cost matrix values** | SOR FN = 8-10 | Kliniczne eksperckie | ✓ Rozsądne, ale subjektywne |

**Krytyka**: Brak grid search, ablation study, czy cross-validation dla hyperparameters.

### 4.4 Brak Cross-Validation

| Typ | Status | Problem |
|-----|--------|---------|
| **K-fold CV** | ❌ Nie | Single train/val split (80/20) – jedna realizacja; brak confidence intervals |
| **Stratified k-fold** | ❌ Nie | Mogłoby być z patient-level separation per fold |
| **Temporal CV** | ❌ Nie | W MIMIC, można byłoby validować na later encounters |

**Rekomendacja**: 5-fold stratified CV z patient-level separation byłoby **duże improvement** dla reliability.

---

## 5. INTERPRETABILNOŚĆ (ATTENTION VISUALISATION)

### 5.1 Attention Weights

| Aspekt | Ocena | Szczegóły |
|--------|-------|----------|
| **Visualization** | ✓ Dobrze | Heatmapy (Fig 8, 10) pokazują attention od [CLS] do tokens. |
| **Case studies** | ✓ Dobry | Complex multi-label (5 referrals) i simple (Nephrology only). Attention concentrate'uje się na relevantnych tokens (CREATININE_Q9 dla Neph). |
| **Interpretability** | ✓ Heurystyk | Autorzy jawnie zaznaczają: "attention does not imply causality" – ważne disclaimer. |

**Ocena**: Attention visualization jest **użyteczna dla audit**, ale **nie dowodzi** causality.

### 5.2 Kauzalność vs. Korelacja

| Stwierdzenie | Właściwe? | Komentarz |
|--------------|-----------|----------|
| "High attention to HGB_LOW → recommendation for Haem" | ⚠️ Korelacyjne | Attention może być spurious – model może uczyć się spurious correlations (np. HGB_LOW → SOR w Synthea, ale nie w reality). |
| "Attention explains prediction" | ⚠️ Słabo | Attention weights są post-hoc; nie wyjaśniają, czy HGB_LOW **faktycznie** wpłynął na output. |
| Potrzeba: ocena feature importance | ❌ Brak | Np. SHAP, integrated gradients, ablation test (usunięcie HGB_Q9 token → zmiana output?) |

**Rekomendacja**: 
- Dodać ablation test: "what if we remove token X from input?"
- Czy prediction zmienia się? O ile?

---

## 6. REPRODUKCYJNA I TRANSPARENTNOŚĆ

| Element | Status | Uwagi |
|---------|--------|-------|
| **Kod source** | ❓ Wspomniany jako "Python scripts" | Nie dołączony do artykułu; link do GitHub byłby kluczowy |
| **Config (YAML/JSON)** | ✓ Wspomniany | vocab, lab_norms, questions.json mają być human-readable |
| **Exact sample counts** | ⚠️ Częściowo | Table I: 260k train, 65k val, ~140 vocab – ale brak breakdown po klasach/źródłach |
| **Model checkpoints** | ✓ Wspomniany | "Checkpoints structured" – ale gdzie dostępne? |
| **Notebooks** | ✓ Wspomniany | "Evaluation notebooks (ROC, PR, calibration, confusion)" – referencja do 05 i 07 |
| **Ethics approval** | ✓ Jawnie stwierdzone | PhysioNet credentialing; nie potrzebne IRB (secondary analysis) |

**Wniosek**: Reproducibility **teoretycznie możliwa**, ale artykuł jest **świeżo opublikowany** – praktyczna reproducibility zależy od dostępu do repozytorium.

---

## 7. TABELARYCZNE PODSUMOWANIE

| Kryterium | Status | Ocena | Uwagi |
|-----------|--------|-------|-------|
| **MLM pre-training** | ✓ Poprawne | 4/5 | Brak ablacji: czy pre-training pomaga? |
| **BERT architektura** | ✓ Rozumna | 4/5 | Zmniejszona (6 layers), ale bez justyfikacji empirycznej |
| **Multi-label BCE loss** | ✓ Poprawne | 5/5 | Prawidłowy dla multi-label; sigmoid per class |
| **Cost-sensitive focal loss** | ✓ Idea dobra | 3/5 | Nie ujawniono równania, γ, dokładne wagi. Brak ablacji. |
| **Patient-level split** | ✓ Doskonałe | 5/5 | Eliminuje leakage; validates na unseen patients |
| **Hybrid corpus** | ✓ Sensowny | 3/5 | Brak breakdown (ile Synthea vs MIMIC?); brak MIMIC-only test |
| **Tokenizacja** | ✓ Rozsądna | 4/5 | Quintiles + critical bands – sensowne; brak szczegółów kalibracji |
| **Class balancing** | ⚠️ Wspomniany | 2/5 | Focal loss + cost matrix, ale brak informacji o ratio klas, data augmentation |
| **ROC/AUPRC/ECE metrics** | ✓ Prawidłowe | 5/5 | Appropriate dla multi-label; wyniki doskonałe |
| **Confusion matrices** | ✓ Dobrze | 4/5 | 3 klasy (SOR, Haem, Neph) – ale SOR jest zbyt doskonały (0 errors?) |
| **Calibration (ECE)** | ✓ Doskonałe | 5/5 | ECE 0.007-0.012 << 0.05; przewidywane prob. są wiarygodne |
| **Attention interpretability** | ✓ Heurystyk | 3/5 | Wizualizacje są intuicyjne, ale brak causality; nie ma ablation test |
| **Temporal modeling** | ❌ Brak | 0/5 | One-encounter input; longitudinal trends są ignorowane |
| **Cross-validation** | ❌ Brak | 1/5 | Single 80/20 split; brak CI, brak k-fold |
| **Hyperparameter tuning** | ⚠️ Adhoc | 2/5 | Standardowe wartości, ale brak grid search; γ nie ujawnionce |
| **Prospective validation** | ❌ Brak | 0/5 | Zaplanowane na future; bez tego nie można wdrażać |
| **Reproducibility** | ✓ Raczej | 3/5 | Config w YAML/JSON, ale kod i checkpoints są prywatne (?) |

---

## 8. REKOMENDACJE KLUCZOWE (PRIORYTETY)

### 🔴 KRYTYCZNE (Pre-deployment)

1. **Separate MIMIC-only hold-out test**
   - Oceń model na MIMIC bez Synthea
   - Czy performance spada? O ile?
   - Jeśli spada drastycznie → Synthea overfitting

2. **Ujawnij hyperparametry focal loss**
   - γ value
   - Dokładne wagi cost matrix
   - Równanie combined BCE + focal

3. **Prospective validation**
   - Najmniej 100 primary care cases (real, not synthetic)
   - A/B test z physician decisions
   - Bezpieczna deployment procedure

### 🟠 WAŻNE (Dla wiarygodności)

4. **Cross-validation z confidence intervals**
   - 5-fold stratified CV, patient-level separation
   - Raport: mean ROC AUC ± std dev per class

5. **Error analysis systematyczny**
   - Class distribution table
   - Per-class breakdown: FP vs FN sources
   - Czy brakuje danych czy overlap symptomów?

6. **Temporal modeling / trend tokens**
   - Minimum: add HGB_RISING/FALLING tokens
   - Albo: LSTM head dla multi-encounter sequences

### 🟡 UŻYTECZNE (Dla robustności)

7. **Ablation studies**
   - Pre-training vs from-scratch
   - Cost-sensitive loss vs standard BCE
   - Attention vs. other interpretability methods (SHAP, integrated gradients)

8. **External dataset evaluation**
   - Jeśli dostępny: test na innym szpitalu (US vs EU, ICU vs primary care)
   - Assess generalization

---

## 9. PODSUMOWANIE METODOLOGICZNE

### ✓ ASPEKTY PRAWIDŁOWE

1. **Multi-label architektura**: Sigmoid per class, niezależne probabilities – prawidłowe dla comorbidity
2. **Patient-level validation**: Eliminuje leakage; metrics odzwierciedlają real deployment scenario
3. **Hybrid corpus**: Synthea (chronic) + MIMIC (acute) zmniejsza bias jednego źródła
4. **Metrics**: ROC, AUPRC, ECE – complete picture discriminatory power + calibration
5. **Safety focus**: Cost-sensitive loss, niższy threshold dla SOR – clinically appropriate
6. **Attention interpretability**: Heatmapy wspierają audit; disclaimer o non-causality jest present

### ⚠️ SŁABE PUNKTY

1. **Cost-sensitive focal loss underspecified** – brakuje równania i γ value
2. **No ablation studies** – nie wiadomo, co daje każdy component (pre-training, cost weighting, focal)
3. **Perfect SOR performance (0 errors)** – podejrzane; likely validation set bias lub klasa zbyt łatwa
4. **No temporal modeling** – jeden encounter snapshot; longitudinal trends ignorowane
5. **Synthea dominance** – brak separate test na MIMIC-only; risk overfitting do generator
6. **Single train/val split** – brak cross-validation; brak confidence intervals
7. **No prospective validation** – planning only; bez tego deployment jest ryzykowny

### 🎯 OGÓLNA OCENA

**Metodologia: 7/10**

- **Dla hackathonu akademickiego**: Very good. Clear methodology, solid metrics, clinically appropriate.
- **Dla production deployment**: Needs improvement. Requires prospective validation, external test, temporal modeling.

**Wnioski dla autorów** (jeśli chcesz wzmocnić):
1. Opublikuj kod + checkpoints (GitHub)
2. Przeprowadź MIMIC-only hold-out test
3. Dodaj k-fold CV z CI
4. Prospective validation 50-100 real cases
5. Temporal extension (trends, longitudinal)

---

## BIBLIOGRAFIA WEWNĘTRZNA

- Banasik, J., Pater, A. (2026). Intelligent Multi-Label Triage for Hematological Comorbidities using BERT. *Hackathon "Built with Opus 4.7"*, Cerebral Valley.
- Johnson, A. E. W., et al. (2023). MIMIC-IV: A freely accessible electronic health record dataset. *Scientific Data*.
- Devlin, J., et al. (2019). BERT: Pre-training of deep bidirectional transformers. NAACL-HLT.
- Synthea: Synthetic patient population. https://synthea.mitre.org

---

**Report compiled: 2026-04-22**
**For: BloodAI Hackathon Project**
**Level: Academic peer-review standard**
