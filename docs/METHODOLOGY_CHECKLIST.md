# Metodologiczna Weryfikacja – Tabela Syntetyczna
## Hackathon "Built with Opus 4.7" | BloodAI | Banasik & Pater 2026

---

## TABELA KRYTERIÓW

| # | Kryterium | Status | Ocena | Uwagi |
|---|-----------|--------|-------|-------|
| **TRENING MODELU** | | | | |
| 1 | MLM pre-training – poprawność podejścia | ✓ | 4/5 | Standardowe (15% maskowania), in-domain adaptation. Brak ablacji: czy pre-training pomaga? |
| 2 | BERT config (6 layers, 256, 8 heads, FFN 1024) | ✓ | 4/5 | Celowo zmniejszona, rozsądna dla ~140 tokenów. Brak justyfikacji empirycznej (vs 12-layer). |
| 3 | Multi-label BCE loss (sigmoid per class) | ✓ | 5/5 | Prawidłowy. Unika softmax constraint, niezależne probabilities. |
| 4 | Cost-sensitive focal loss – logika | ⚠️ | 3/5 | **PROBLEM**: Nie ujawniono równania, γ value, konkretne wagi. Brak ablacji (cost vs focal impact). |
| 5 | Learning rates (10⁻⁴ MLM, 2×10⁻⁵ FT) | ✓ | 5/5 | Standardowe, prawidłowe schowanie. |
| 6 | Batch sizes (64, 32/64) | ✓ | 4/5 | Rozsądne dla 260k samples. Bez justyfikacji. |
| 7 | Liczba epok (15 MLM, 5 FT) | ⚠️ | 2/5 | Arbitralne. Brak validation loss curve, early stopping? |
| **PRZYGOTOWANIE DANYCH** | | | | |
| 8 | Patient-level split (80/20) – eliminacja leakage | ✓ | 5/5 | Doskonałe. Każdy pacjent całkowicie w train lub val. Validates na unseen patients. |
| 9 | Stratified sampling po klasach | ⚠️ | 3/5 | Wspominane "approximately", ale brak szczegółów. Każda klasa w train i val? |
| 10 | Hybrydowy corpus (Synthea + MIMIC) – bezpieczeństwo | ✓ | 3/5 | Zmniejsza bias, ale **brakuje info**: ile Synthea vs MIMIC (%)? |
| 11 | Overfitting do Synthea (syntetyczne wzorce) | ❌ | 1/5 | **RYZYKO WYSOKIE**. Brak separate MIMIC-only test. Future work, ale nic teraz. |
| 12 | Quantyzacja parametrów (quintiles, critical) | ✓ | 4/5 | Rozsądna (token HGB_Q4 zamiast 7.5 g/dL). Brakuje szczegółów kalibracji quintiles. |
| 13 | Reference ranges age/sex dependent | ✓ | 4/5 | Wspominane (lab_norms.json), ale czy quintiles per group? Niejasne. |
| 14 | Class balancing – informacje | ⚠️ | 2/5 | Focal loss + cost matrix wspominane. **Brakuje**: ratio klas (% per label). Data augmentation wspomniany ale niezdefiniowany. |
| **METRYKI EWALUACJI** | | | | |
| 15 | ROC AUC (one-vs-rest) – właściwy dla multi-label | ✓ | 5/5 | Tak. Wyniki doskonałe (SOR=1.00, Haem=0.94, Neph=0.95). |
| 16 | AUPRC – dla imbalanced klas | ✓ | 5/5 | Tak, prawidłowy. High AUPRC dla SOR, Haem confirms low false alarms. |
| 17 | ECE (Expected Calibration Error) | ✓ | 5/5 | Doskonałe (0.007–0.012 << 0.05). Predicted probabilities wiarygodne dla clinical use. |
| 18 | Confusion matrices per-class | ✓ | 4/5 | 3 reprezentatywne klasy (SOR, Haem, Neph). **ALE**: SOR perfect (0 errors) – podejrzane. |
| 19 | Patient-level validation (no per-encounter leakage) | ✓ | 5/5 | Tak, prawidłowo opisane. Metrics reflect generalization do unseen patients. |
| 20 | Subset accuracy | ✓ | 5/5 | Słusznie pomijany (multi-label subset acc typowo niska). |
| **POTENCJALNE PROBLEMY** | | | | |
| 21 | Overfitting do Synthea (generator patterns) | ❌ | 1/5 | **KRYTYCZE**. Brak MIMIC-only hold-out test. Performance mogą być optimistycznie skłonione. |
| 22 | Temporal modeling – brak longitudinal | ❌ | 1/5 | One-encounter snapshot. Trendy (HGB: 6.5→7.0 vs 7.0→6.5) ignorowane. Clinically relevant. |
| 23 | Cross-validation – brak k-fold | ❌ | 1/5 | Single 80/20 split. Brak confidence intervals, variance estimates. |
| 24 | Hyperparameter tuning – grid search | ❌ | 2/5 | Adhoc selection. Standardowe wartości, ale brak systematic search. |
| 25 | Prospective validation – real deployment test | ❌ | 0/5 | Zaplanowane na future. Bez tego deployment jest nieuzasadniony. |
| **INTERPRETABILNOŚĆ** | | | | |
| 26 | Attention weights visualization | ✓ | 4/5 | Dobry (Fig 8, 10). Heatmapy pokazują które tokeny model attention'uje. |
| 27 | Case studies (complex + simple) | ✓ | 5/5 | Doskonałe. 5-referral case i Nephrology-only – intuicyjnie wyjaśniają output. |
| 28 | Disclaimer: attention ≠ causality | ✓ | 5/5 | Jawnie stwierdzone – ważne. |
| 29 | Feature importance (ablation, SHAP, etc.) | ❌ | 0/5 | **BRAK**. Co jeśli usuniemy CREATININE_Q9 token? Output się zmienia? O ile? |
| 30 | Causal analysis – ground truth triggers | ❌ | 2/5 | Attention jest heurystyk. Brak mechanizmu do verify causality. |
| **REPRODUKCYJNA** | | | | |
| 31 | Kod źródłowy dostępny (GitHub) | ⚠️ | 2/5 | Wspominany jako "Python scripts", ale nie linkowany. Prywatny? |
| 32 | Config (YAML/JSON) human-readable | ✓ | 4/5 | Wspominany (lab_norms.json, questions.json). Struktura jest jasna. |
| 33 | Exact sample counts per class | ⚠️ | 2/5 | Table I: 260k train, 65k val. **Brakuje**: breakdown per klasa, per źródło (Synthea vs MIMIC %). |
| 34 | Model checkpoints dostępne | ⚠️ | 2/5 | Wspominane jako "structured", ale gdzie? Link do repo? |
| 35 | Evaluation notebooks reproducible | ⚠️ | 3/5 | Ref. notebooks 05, 07, ale czy public accessible? |
| **ETYKA I RIGOR** | | | | |
| 36 | Ethics approval / PhysioNet credentialing | ✓ | 5/5 | Jawnie stwierdzone. Secondary analysis, brak dodatkowego IRB. |
| 37 | Safety-first mindset (SOR priority) | ✓ | 5/5 | Excellent. High cost FN dla SOR, niższy threshold – clinically appropriate. |
| 38 | Limitations jawnie zadeklarowane | ✓ | 5/5 | Section IV czyta się dobrze: Synthea synthetic, MIMIC US-centric, brak prospective validation, no temporal. |
| 39 | Future work roadmap | ✓ | 4/5 | Jasne (cost matrix impact, question bank improvement, prospective validation). Brakuje: external dataset, temporal modeling. |

---

## SYNTETYCZNA OCENA NA WYMIARACH

| Wymiar | Ocena | Justyfikacja |
|--------|-------|--------------|
| **Poprawność Metodologiczna** | 7/10 | Multi-label architektura OK. MLM+BCE+focal sound. Patient-level split excellent. ALE: focal loss underspecified, no ablation, one 80/20 split. |
| **Solidność Danych** | 6/10 | Hybrid corpus rozsądny. ALE: brak breakdown %, overfitting Synthea risk, brak separate MIMIC test. |
| **Rigor Ewaluacji** | 8/10 | ROC, AUPRC, ECE appropriate. Confusion matrices good. ALE: SOR perfect (podejrzane), single split (no CV), no external test. |
| **Interpretabilność** | 6/10 | Attention heatmapy intuicyjne. Disclaimer o non-causality. ALE: brak ablation test, feature importance analysis. |
| **Reproducibility** | 5/10 | Config w YAML/JSON opisane. ALE: kod prywatny (?), checkpoints lokalizacja niejasna, brak exact per-class breakdown. |
| **Deployment Readiness** | 3/10 | Safety focus (SOR cost), calibration excellent. ALE: **brak prospective validation, brak MIMIC-only test, brak temporal modeling**. NOT ready for production. |

---

## PLAN DZIAŁAŃ – PRIORYTETY NAPRAWCZE

### 🔴 KRYTYCZNE (pre-deployment – MUSI być zrobione)

```
Task 1: Separate MIMIC-only hold-out test
├─ Podziel validation set: 50% MIMIC, 50% Synthea (jeśli mix)
├─ Oceń model na MIMIC-only subset
├─ Report: ROC AUC, ECE per class (MIMIC vs full val)
└─ DECISION: Jeśli MIMIC performance << full → Synthea overfitting (nie deploy)

Task 2: Ujawnij hyperparametry cost-sensitive focal loss
├─ Równanie: L_combined = w_cost * BCE + γ * FocalLoss
├─ γ value (np. 2.0)
├─ Cost matrix C_ij complete (8×8 table)
├─ Ablation: cost-only vs focal-only vs combined
└─ Reproducibility: anyone can rebuild model exactly

Task 3: Prospective validation (minimum)
├─ Collect 50–100 real primary care cases (not Synthea, not ICU-skewed MIMIC)
├─ Blind eval: model prediction vs physician decision
├─ Agreement rate, clinically important disagreements
├─ Safety: any missed SOR cases? Any dangerous FP?
└─ NOT acceptable until: sensitivity(SOR) ≥ 95% on real data
```

### 🟠 WAŻNE (wiarygodność – powinna być zrobione pre-publication)

```
Task 4: 5-fold stratified cross-validation
├─ Patient-level stratified k-fold (k=5)
├─ Report: mean ROC AUC ± std per class
├─ Confidence intervals dla ECE
└─ Compare: full model variance vs single 80/20 split

Task 5: Systematic error analysis
├─ Per-class distribution table (% positive samples per class)
├─ FP vs FN breakdown: missing data? Overlap symptoms? Threshold issue?
├─ Examples: 5 top FN cases (missed referrals), 5 top FP cases (false alarms)
├─ For each: "root cause" annotation
└─ Feed results → iterative improvement of question bank

Task 6: MIMIC vs Synthea breakdown
├─ Report: % of training samples from each source
├─ Separate metrics: train on Synthea only, test on MIMIC → generalization gap?
├─ If gap is large (e.g., 20%+ drop) → issue identified, needs addressing
└─ Publication: include this comparison transparently
```

### 🟡 UŻYTECZNE (robustność – nice-to-have)

```
Task 7: Ablation studies
├─ Pre-training vs from-scratch BERT
├─ Cost-sensitive loss vs standard BCE
├─ Focal loss γ sensitivity (0.5, 1.0, 2.0, 3.0)
├─ Attention mechanism vs simple logistic regression (baseline)
└─ Results: figure out what contributes to final performance

Task 8: Temporal extension
├─ Add trend tokens (HGB_RISING, HGB_FALLING) based on consecutive encounters
├─ Or: LSTM head for multi-encounter sequences
├─ Evaluate: does temporal info improve SOR sensitivity?
└─ Publishable: "Temporal Modeling for Triage Robustness"

Task 9: External dataset validation
├─ If available: test on different hospital, different country (EU vs US)
├─ Assess generalization across populations
├─ Document domain adaptation needs
└─ Reality check: is model robust or does it overfit to MIMIC/Synthea distribution?
```

---

## PODSUMOWANIE EXECUTIVE

### Siła projektu ✓
- **Multi-label architektura**: Prawidłowa dla comorbidity
- **Patient-level validation**: Eliminuje leakage, metrics relevant dla deployment
- **Safety focus**: Cost-sensitive loss, high SOR sensitivity (0 FN) – clinically prioritized
- **Calibration**: ECE 0.007–0.012 doskonała – trustworthy probabilities
- **Transparency**: Limitations jasno stwierdzone; Safety as primary goal

### Słabości projektu ❌
- **Underspecified loss**: Focal loss parameters (γ, exact weights) nie ujawnione
- **Synthea risk**: Brak MIMIC-only test – métryki mogą być optimistycznie skłonione
- **One split**: Single 80/20 fold, brak cross-validation, brak confidence intervals
- **No temporal**: Snapshot encounters only; longitudinal trends ignorowane
- **No prospective**: Bez real-world validation, deployment jest nieuzasadniony

### Dojrzałość dla deployment
- **Hackathon academic**: Very good ✓ (7/10)
- **Production clinical**: Not ready ❌ (3/10)

### Top 3 Actions
1. **Separate MIMIC-only test** – verify no Synthea overfitting
2. **Prospective validation 50+ real cases** – safety confirmation
3. **5-fold CV + confidence intervals** – reliability quantification

---

## REFERENCJE

- Full methodology review: `docs/METHODOLOGY_REVIEW.md`
- Paper: `docs/paper.pdf`
- CLAUDE.md: BloodAI architecture & project plan
