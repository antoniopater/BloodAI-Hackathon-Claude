---
name: bloodai-day2-frontend
description: "BloodAI hackathon Day 2: React frontend — form, triage visualization, plain-language parameter explainer, attention heatmap. Progress tracking and end-of-day assessment."
---

# Day 2: Frontend Core + Parameter Explainer

## Goal for the day
By end of day: working React UI with lab input form, plain-language parameter explanations, 8-class triage visualization with attention heatmap, and adaptive interview. Connected to the Day 1 backend.

## Morning: check Day 1 status
- [ ] Training finished? Check metrics (ROC AUC, ECE)
- [ ] `/predict` endpoint works? Test a few scenarios
- [ ] If the model underperforms — tune thresholds, don't panic

## Task checklist

### Block 1: React Setup + Input Form (2–3h)
- [ ] React app (Vite or Next.js)
- [ ] Layout: dark theme, medical/clinical design
- [ ] Lab results form:
  - Fields: age, sex, HGB, HCT, PLT, MCV, WBC, Creatinine, ALT
  - Validation: min/max per parameter
  - Colored borders by status: ✅ in range (green), ⚠️ out of range (yellow), 🚨 critical (red)
  - Demo presets: "Nephrology", "Multi-label", "Normal" — one-click fill
- [ ] "Analyze" button → POST to `/predict`

### Block 2: Parameter Explainer — KEY FEATURE (2–3h)
- [ ] Each parameter field: expandable panel "What does this mean?"
- [ ] Two information levels:
  1. **Static** (always visible): parameter name + one-line "what it does"
  2. **Dynamic** (on "Explain" click): Opus 4.7 generates contextual text

Example static blurbs (hardcoded, fast):
```
HGB: "Hemoglobin — protein that carries oxygen in blood. Low = possible anemia."
HCT: "Hematocrit — what fraction of blood is red blood cells."
PLT: "Platelets — help blood clot. Too few = bleeding risk."
MCV: "Mean red cell volume — helps classify types of anemia."
WBC: "White blood cells — immune defense. High = possible infection or inflammation."
Creatinine: "Muscle waste cleared by kidneys. High = kidneys may be struggling."
ALT: "Liver enzyme. High = possible liver injury."
```

- [ ] Dynamic explanations (Opus 4.7 API):
  - Prompt: "Patient {age} years, {sex}. Parameter {name} = {value} {unit} (reference: {low}-{high}). Explain in plain language what this means for this patient, max 2 sentences. Do not diagnose or alarm."
  - On-demand (button), not on every keystroke
  - Cache: keep generated text in state for the session
  - Loading: skeleton / typing animation while generating

- [ ] Combination summary (after "Analyze"):
  - Opus 4.7 receives ALL parameters → short summary of interactions
  - e.g. "Low hemoglobin with high creatinine may suggest anemia of chronic kidney disease"

### Block 3: Triage Visualization (2h)
- [ ] 8 horizontal probability bars (animated, colored)
- [ ] Threshold marker on each bar
- [ ] Classes above threshold marked as "recommended"
- [ ] Attention heatmap:
  - Vertical bar chart or heatmap
  - Parameters sorted by attention high → low
  - Color: red (high attention) → blue (low)
  - Tooltip with attention score

### Block 4: Adaptive Interview (1h)
- [ ] If parameter out of range → question from bank (GET `/questions/{param}`)
- [ ] UI: modal or inline card with question + yes/no
- [ ] Answer appended as token → re-predict
- [ ] Max 3 questions (avoid fatigue)

### Block 5: Animations + Polish (1h)
- [ ] Smooth transitions: input → loading (spinner + "Running BERT...") → results
- [ ] Fade-in on results
- [ ] Typing animation on Opus explanations
- [ ] Basic mobile responsive layout

## End-of-day self-assessment

| Question | Score |
|----------|-------|
| Does the form look professional and work correctly? | /5 |
| Is the parameter explainer understandable for non-medical users? | /5 |
| Is triage visualization (bars + attention) clear? | /5 |
| Is Opus 4.7 integrated with explanations? | /5 |
| Does the full flow work end-to-end (input → predict → results)? | /5 |

**25/25** = frontend ready; tomorrow focus on Opus features  
**20–24** = good; light polish tomorrow morning  
**15–19** = simplify — core flow first; attention and Opus can wait  
**<15** = alarm — finish frontend tomorrow morning

## Fallback
- Parameter explainer: if Opus API fails → static blurbs are enough
- Attention heatmap: simple bar chart instead of fancy heatmap
- Adaptive interview: optional; don't block triage
