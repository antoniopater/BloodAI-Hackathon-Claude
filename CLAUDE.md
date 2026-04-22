# BloodAI — Intelligent Multi-Label Triage System

## Projekt
Hackathon "Built with Opus 4.7" (Cerebral Valley). Solo. Deadline: 26.04.2026.

**Elevator pitch**: "Zeskanuj wyniki badań krwi → AI tłumaczy co oznaczają → mówi do jakiego specjalisty iść → pokazuje kolejki NFZ z terminami."

## Fundamenty naukowe
Paper: "Intelligent Multi-Label Triage for Hematological Comorbidities using BERT" (Banasik, Pater).
Pełna treść: `docs/paper.pdf`
- Model BERT: 6 layers, 256 hidden, 8 heads, FFN 1024, vocab ~140 tokenów
- Dane: hybrid corpus Synthea + MIMIC-III/IV, 260k encounters, patient-level split 80/20
- 8 klas: POZ, Gastroenterologia, Hematologia, Nefrologia, SOR, Kardiologia, Pulmonologia, Hepatologia
- Loss: BCEWithLogitsLoss + Cost-Sensitive Focal Loss (SOR miss = 10)
- Metryki: ROC AUC (SOR=1.00, Nephrology=0.95, Haematology=0.94), ECE < 0.012

## Architektura aplikacji

```
FRONTEND (React/Next.js)
├── 📷 Skan wyników (camera/PDF) → Opus 4.7 Vision OCR
├── 📝 Formularz z tłumaczem parametrów prostym językiem
├── 📈 Trendy (porównanie 2+ zestawów wyników)
├── 🔬 Wyniki triażu (8 klas + attention heatmap)
│   ├── 👤 Tryb pacjenta (uproszczony, bez surowych liczb)
│   └── 🩺 Tryb kliniczny (pełne dane, attention, ECE)
├── 🤖 Wyjaśnienie Opus 4.7 (kontekstowe, dynamiczne)
└── 🏥 Specialist Finder (NFZ API + prywatni)

BACKEND (FastAPI + PyTorch)
├── POST /predict → 8 prawdopodobieństw + attention weights
├── POST /scan → Opus 4.7 Vision → ekstrakcja wartości + norm z kartki
├── POST /explain → Opus 4.7 → tłumaczenie prostym językiem
├── GET  /nfz/queues → proxy do API NFZ Terminy Leczenia
├── POST /trends → porównanie 2+ zestawów wyników
├── GET  /lab_norms → normy referencyjne
└── GET  /questions/{param} → pytania adaptive interview

ML PIPELINE
├── data/prepare_corpus.py → Synthea + MIMIC → tokeny + labels
├── model/tokenizer.py → word-level, vocab ~140
├── model/pretrain_mlm.py → MLM, 15 epochs, lr 1e-4
├── model/finetune_multilabel.py → 5 epochs, lr 2e-5, focal loss
└── model/evaluate.py → ROC, PR, ECE, confusion matrices
```

## Plan pracy — pełna dokumentacja
Szczegółowy plan dzień po dniu: `docs/hackathon-plan.md`

## Skills (czytaj przed każdym dniem pracy!)
Każdy dzień ma swój skill z checklistą, self-assessment, i fallback planem:
- `skills/day1-pipeline/SKILL.md` — ML pipeline + FastAPI backend
- `skills/day2-frontend/SKILL.md` — React UI + tłumacz parametrów
- `skills/day3-opus/SKILL.md` — Opus 4.7: skan, wyjaśnienia, second opinion
- `skills/day4-nfz-dualmode/SKILL.md` — NFZ API + dual mode + trendy
- `skills/day5-demo/SKILL.md` — deploy, demo prep, pitch
- `skills/scoring/SKILL.md` — samoocena wg kryteriów hackathonu

## Kryteria oceny hackathonu
- **Impact (30%)**: real-world potential, kto korzysta, problem statement fit
- **Demo (25%)**: działa na żywo, "wow" moment, cool to watch
- **Opus 4.7 Use (20%)**: kreatywne użycie, beyond basic, zaskoczenie
- **Depth & Execution (20%)**: iteracja, jakość, craft

## Zasady (dyskwalifikacja!)
- ❗ Wszystko MUSI być open source
- ❗ Cała praca NOWA (started during hackathon)
- ❗ Solo (1 osoba)
- ❗ Brak kradzionego kodu/danych/assetów

## Kluczowe API
- NFZ Terminy Leczenia: `https://api.nfz.gov.pl/app-itl-api/queues?case=1&province=07&benefit=PORADNIA+NEFROLOGICZNA`
- Anthropic: `https://api.anthropic.com/v1/messages` (model: claude-sonnet-4-20250514)
- NFZ API jest publiczne, bez klucza, bezpłatne

## Technologie
- Frontend: React, Tailwind, Leaflet (mapa), recharts
- Backend: FastAPI, PyTorch, uvicorn
- Deploy: Vercel (frontend) + Railway (backend)
- Licencja: MIT

## Priorytety (jeśli brakuje czasu)
**MUST**: pipeline ML + /predict + formularz + wyniki triażu + tłumacz parametrów + NFZ kolejki
**SHOULD**: skan kamerą, dual mode, attention heatmap, Opus wyjaśnienia
**NICE**: trendy, second opinion, raport PDF, Google Places

## Jak pracować
1. Na start dnia: przeczytaj odpowiedni `skills/dayN/SKILL.md`
2. Pracuj wg checklisty z tego skilla
3. Na koniec dnia: zrób self-assessment z tego skilla
4. Commituj często z meaningful messages
5. Jeśli coś nie działa po 30 min — uprość
6. W dowolnym momencie: `skills/scoring/SKILL.md` → pełna ocena projektu
