---
name: bloodai-day5-demo
description: "BloodAI hackathon Day 5: demo preparation, deploy, pitch. Everything must work live without stalling. Backup video. Final self-assessment."
---

# Day 5: Demo Prep + Deploy

## Goal for the day
By end of day: deployed app, rehearsed 2-minute pitch, 4 demo scenarios tested, backup video recorded.

## Morning: Full E2E Test (2h)
- [ ] Walk the full flow from scratch while screen recording:
  1. Open app → scan lab result sheet
  2. OCR preview → confirm
  3. Parameter explainer (click "what this means" on 2–3 parameters)
  4. Analyze → triage results + attention
  5. Toggle mode (patient ↔ clinician)
  6. Opus explanation
  7. NFZ queues → show facilities
  8. (optional) Trends — compare with older results
- [ ] Note what stalls, what is slow, what looks bad
- [ ] Fix critical bugs (max 1h for fixes)

## Deploy (1–2h)
- [ ] Backend:
  - Railway / Render / Fly.io
  - Ensure: model loads at startup (cold start < 30s)
  - Health check: `GET /health`
  - CORS set to frontend domain
- [ ] Frontend:
  - Vercel (simplest for React/Next.js)
  - Environment variables: API URL, Anthropic API key
- [ ] Deploy test: phone + laptop → full flow works

## Demo Script — 4 scenarios (prepare and rehearse)

### Scenario 1: 📷 "Sheet scan" (WOW moment — lead with this!)
```
"Imagine: a patient leaves the lab with a paper printout.
They don't know what the numbers mean. They don't know who to see.
[takes phone photo of the sheet]
The system reads the results and compares to reference ranges FROM THAT sheet...
[shows auto-fill + verification]
...and explains each parameter in plain language.
[clicks 'What does this mean?' on creatinine]"
```

### Scenario 2: 🔬 "Simple case — nephrology"
```
"Male, 60, high creatinine 4.8.
[manual entry or preset]
BERT trained on 260k clinical encounters
immediately flags Nephrology at 99% probability.
[shows attention map]
Look — the model attends heavily to CREATININE_Q9.
That's interpretable AI — the clinician sees WHY.
[switches to patient mode]
The patient sees: 'We recommend a nephrology consult.'"
```

### Scenario 3: 🏥 "NFZ queues" (killer feature)
```
"But where to go? The app calls the public NFZ API...
[clicks 'Find specialist']
Nephrology clinic in Warsaw — NFZ: first slot in 47 days.
Private: about 3 days.
[shows map with pins]
The patient can call or navigate immediately.
In Poland, average wait for a specialist is ~4 months.
We compress the decision to about 60 seconds."
```

### Scenario 4: 🚨 "Multi-label — woman 70" (show depth)
```
"Woman 70, severe anemia, kidney dysfunction,
infection, cardiac symptoms.
['Multi-label' preset]
The model predicts 5 specialties at once —
true multi-label, not single-label.
Opus 4.7 verifies: 'I agree with BERT routing.'
Now watch attention — spread across many tokens
because this is a complex case."
```

## Pitch — 2 minutes (memorize)

```
[10s] PROBLEM:
"In Poland patients wait on average 4 months for a specialist.
190 days for an endocrinologist. It starts with a lab printout
they cannot understand."

[20s] SOLUTION:
"BloodAI: scan blood test results — AI explains what they mean,
tells you which specialist to see, and shows NFZ queues with wait times."

[60s] DEMO:
[Scenario 1: scan → auto-fill → explain → triage → NFZ]

[20s] TECH:
"Under the hood: a dedicated BERT trained on clinical data
with cost-sensitive loss and attention interpretability.
NOT an LLM wrapper — Opus 4.7 is an intelligence layer ON TOP:
Vision for OCR, explanations, verification, trend analysis."

[10s] DIFFERENTIATOR:
"No existing app combines a validated medical model,
plain-language explanations, and live NFZ queue data."
```

## Backup Video (1h)
- [ ] Record full flow (OBS / screen record)
- [ ] 2–3 minutes, clean run
- [ ] Upload to YouTube/Google Drive (unlisted)
- [ ] Link in README

## Final Checklist
- [ ] Public GitHub repo
- [ ] README complete: description, architecture, setup, screenshots
- [ ] MIT LICENSE file
- [ ] requirements.txt / package.json up to date
- [ ] No hardcoded secrets (use env vars)
- [ ] App works on deploy URL
- [ ] App works on phone (mobile test)
- [ ] Backup video recorded

## FINAL SELF-ASSESSMENT — Hackathon Scorecard

```
╔══════════════════════════════════════════════════╗
║           BLOODAI — FINAL ASSESSMENT             ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  IMPACT (30%)                    /10  →    /3.0  ║
║  ├─ Real problem (PL queues):         /10        ║
║  ├─ Who benefits (patient+doctor):    /10        ║
║  ├─ Product proximity:                /10        ║
║  └─ Problem statement fit (#1):       /10        ║
║                                                  ║
║  DEMO (25%)                      /10  →    /2.5  ║
║  ├─ Works end-to-end live:            /10        ║
║  ├─ "Wow" moment (scan/NFZ):          /10        ║
║  └─ Visually professional:            /10        ║
║                                                  ║
║  OPUS 4.7 USE (20%)             /10  →    /2.0  ║
║  ├─ Number of use cases (aim 4+):     /10        ║
║  ├─ Beyond basic (not chatbot):     /10        ║
║  └─ Surprise (ML+LLM hybrid):        /10        ║
║                                                  ║
║  DEPTH & EXECUTION (20%)        /10  →    /2.0  ║
║  ├─ Code and architecture quality:   /10        ║
║  ├─ Edge cases and error handling:   /10        ║
║  └─ Iteration and craft:             /10        ║
║                                                  ║
║  ══════════════════════════════════════════════   ║
║  TOTAL:                              /10.0       ║
╚══════════════════════════════════════════════════╝
```

## Last tip
On demo day: **don't explain the stack — SHOW it.**
Less talking, more clicking. Judges remember the moment
you photographed the sheet and the system read it,
not a BERT architecture slide.
