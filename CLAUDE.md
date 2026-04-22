# BloodAI — Intelligent Multi-Label Triage System

## Project
Hackathon "Built with Opus 4.7" (Cerebral Valley). Solo. Deadline: 26.04.2026.

**Elevator pitch**: "Scan blood test results → AI explains what they mean → tells you which specialist to see → shows NFZ queues with wait times."

## Scientific foundation
Paper: "Intelligent Multi-Label Triage for Hematological Comorbidities using BERT" (Banasik, Pater).
Full text: `docs/paper.pdf`
- BERT model: 6 layers, 256 hidden, 8 heads, FFN 1024, vocab ~140 tokens
- Data: hybrid corpus Synthea + MIMIC-III/IV, 260k encounters, patient-level split 80/20
- 8 classes: POZ, Gastroenterology, Hematology, Nephrology, ER, Cardiology, Pulmonology, Hepatology
- Loss: BCEWithLogitsLoss + Cost-Sensitive Focal Loss (ER miss = 10)
- Metrics: ROC AUC (ER=1.00, Nephrology=0.95, Haematology=0.94), ECE < 0.012

## Application architecture

```
FRONTEND (React/Next.js)
├── 📷 Result scan (camera/PDF) → Opus 4.7 Vision OCR
├── 📝 Form with plain-language parameter explanations
├── 📈 Trends (compare 2+ result sets)
├── 🔬 Triage results (8 classes + attention heatmap)
│   ├── 👤 Patient mode (simplified, no raw numbers)
│   └── 🩺 Clinical mode (full data, attention, ECE)
├── 🤖 Opus 4.7 explanation (contextual, dynamic)
└── 🏥 Specialist Finder (NFZ API + private providers)

BACKEND (FastAPI + PyTorch)
├── POST /predict → 8 probabilities + attention weights
├── POST /scan → Opus 4.7 Vision → extract values + reference ranges from sheet
├── POST /explain → Opus 4.7 → plain-language explanation
├── GET  /nfz/queues → proxy to NFZ Treatment Dates API
├── POST /trends → compare 2+ result sets
├── GET  /lab_norms → reference ranges
└── GET  /questions/{param} → adaptive interview questions

ML PIPELINE
├── data/prepare_corpus.py → Synthea + MIMIC → tokens + labels
├── model/tokenizer.py → word-level, vocab ~140
├── model/pretrain_mlm.py → MLM, 15 epochs, lr 1e-4
├── model/finetune_multilabel.py → 5 epochs, lr 2e-5, focal loss
└── model/evaluate.py → ROC, PR, ECE, confusion matrices
```

## Work plan — full documentation
Day-by-day plan: `docs/hackathon-plan.md`

## Skills (read before each workday!)
Each day has a skill with checklist, self-assessment, and fallback plan:
- `skills/day1-pipeline/SKILL.md` — ML pipeline + FastAPI backend
- `skills/day2-frontend/SKILL.md` — React UI + parameter explainer
- `skills/day3-opus/SKILL.md` — Opus 4.7: scan, explanations, second opinion
- `skills/day4-nfz-dualmode/SKILL.md` — NFZ API + dual mode + trends
- `skills/day5-demo/SKILL.md` — deploy, demo prep, pitch
- `skills/scoring/SKILL.md` — self-assessment against hackathon criteria

## Hackathon judging criteria
- **Impact (30%)**: real-world potential, who benefits, problem statement fit
- **Demo (25%)**: works live, "wow" moment, cool to watch
- **Opus 4.7 Use (20%)**: creative use, beyond basic, surprise factor
- **Depth & Execution (20%)**: iteration, quality, craft

## Rules (disqualification!)
- ❗ Everything MUST be open source
- ❗ All work NEW (started during hackathon)
- ❗ Solo (1 person)
- ❗ No stolen code/data/assets

## Key APIs
- NFZ Treatment Dates: `https://api.nfz.gov.pl/app-itl-api/queues?case=1&province=07&benefit=PORADNIA+NEFROLOGICZNA`
- Anthropic: `https://api.anthropic.com/v1/messages` (model: claude-sonnet-4-20250514)
- NFZ API is public, no key, free

## Tech stack
- Frontend: React, Tailwind, Leaflet (map), recharts
- Backend: FastAPI, PyTorch, uvicorn
- Deploy: Vercel (frontend) + Railway (backend)
- License: MIT

## Priorities (if time runs short)
**MUST**: ML pipeline + /predict + form + triage results + parameter explainer + NFZ queues
**SHOULD**: camera scan, dual mode, attention heatmap, Opus explanations
**NICE**: trends, second opinion, PDF report, Google Places

## How to work
1. Start of day: read the matching `skills/dayN/SKILL.md`
2. Work through that skill's checklist
3. End of day: run self-assessment from that skill
4. Commit often with meaningful messages
5. If something fails after 30 minutes — simplify
6. Anytime: `skills/scoring/SKILL.md` → full project evaluation
