---
name: bloodai-day3-opus
description: "BloodAI hackathon Day 3: Opus 4.7 integration — camera/PDF scan, contextual explanations, second opinion, smart interview. Critical day for 'Opus 4.7 Use' points."
---

# Day 3: Opus 4.7 Integration + Scan

## Goal for the day
By end of day Opus 4.7 is used in at least 4 ways: (1) Vision OCR of lab sheet, (2) result explanations, (3) context / combination analysis, (4) second opinion over BERT. This day wins the "Opus 4.7 Use (20%)" category.

## Task checklist

### Block 1: Camera/PDF Scan — lab OCR (3–4h) ⭐ PRIORITY
- [ ] Frontend: upload component (drag & drop + camera input)
```html
<input type="file" accept="image/*,application/pdf" capture="environment" />
```
- [ ] Backend endpoint `POST /scan`:
  - Input: base64 image or PDF
  - Send to Opus 4.7 with prompt:

```
OCR prompt:
"You are an expert at reading laboratory blood test reports.
The image/PDF shows a lab result sheet.

Extract:
1. Each lab parameter: name, value, unit
2. Reference ranges printed on the sheet (if visible)
3. Patient data: age, sex (if visible)
4. Lab name (if visible)

Reply ONLY as JSON:
{
  "patient": {"age": null, "sex": null},
  "lab_name": null,
  "parameters": [
    {
      "name": "HGB",
      "value": 14.2,
      "unit": "g/dL",
      "reference_low": 12.0,
      "reference_high": 17.5,
      "source": "from_sheet"
    }
  ],
  "confidence": "high|medium|low",
  "notes": "any issues with readability"
}

If unsure about a value — set confidence to 'low' and add a note.
Do not guess — better to omit than return a wrong value."
```

- [ ] Frontend: review screen "We recognized these values — review and confirm"
  - Table: parameter | recognized value | sheet reference | default reference | status
  - Editable fields (user can correct)
  - "Confirm and analyze" button
- [ ] Fallback: if OCR confidence = "low" → highlight yellow, ask for verification
- [ ] Fallback: if reference ranges unreadable → use defaults from lab_norms.json, show "using default reference ranges"
- [ ] PDF: Opus 4.7 document input (base64)

### Block 2: Contextual explanations — summary (1–2h)
- [ ] Backend endpoint `POST /explain`:
  - Input: triage results + attention + lab values + demographics
  - Two prompt modes:

```
Patient-mode prompt:
"Based on this patient's blood tests ({age} years, {sex}):
{parameter list with values and status}

The AI model flagged these specialties:
{specialty list with flags}

Explain in plain language (max 150 words):
- What might be going on (without alarming)
- Why these specialties
- What the patient should do next
Do not diagnose. Always recommend seeing a doctor."

Clinical-mode prompt:
"BERT multi-label triage for patient ({age}, {sex}):
{parameters with quantiles and attention values}
Probabilities: {8 classes with values}
Attention top-3: {highest-attention tokens}

Give a short clinical interpretation (max 100 words):
- Dominant attention signals
- Urgency suggestion (stable/urgent/emergent)
- Optional dual review if >1 specialty >0.5"
```

### Block 3: Second Opinion — Opus checks BERT (1h)
- [ ] Backend: after BERT prediction, optionally send the same case to Opus 4.7:

```
Second-opinion prompt:
"Patient {age} years, {sex}. Lab results:
{parameters with values}

ML BERT model suggested:
{specialties with probabilities}

Do you agree with this routing?
Reply ONLY as JSON:
{
  "agree": true/false,
  "disagreements": [
    {"class": "...", "bert_prob": 0.xx, "your_assessment": "...", "reason": "..."}
  ],
  "additional_concerns": "...",
  "confidence": "high|medium|low"
}
Do not guess — if data is insufficient, say so."
```

- [ ] Frontend: if Opus disagrees → alert "AI triage and AI verifier differ — consult a physician"
- [ ] Strong demo line: "built-in verification layer"

### Block 4: Smart Interview (1h)
- [ ] Instead of only a fixed question bank, Opus generates follow-ups:

```
Interview prompt:
Patient {age} years, {sex}. Parameter {name} = {value} (reference: {low}-{high}).
Other results: {context}
Generate ONE short follow-up question in English that helps triage.
Reply ONLY as JSON:
{"question": "...", "token_yes": "...", "token_no": "..."}
```

- [ ] Max 2–3 questions per session
- [ ] Answer affects re-predict (append token to sequence)

### Block 5: PDF report (1h — optional)
- [ ] Generate PDF: patient data, results, triage, attention, explanation
- [ ] For printout / to bring to doctor
- [ ] Disclaimer on every page

## End-of-day self-assessment

| Question | Score |
|----------|-------|
| Does camera/PDF scan recognize results correctly? | /5 |
| Are reference ranges from the sheet read (or does fallback work)? | /5 |
| Is the Opus explanation clear and on-point? | /5 |
| Does second opinion work and show disagreements? | /5 |
| How many Opus 4.7 use cases? (target: min 4) | /5 |

**Count Opus 4.7 use cases:**
1. ☐ Vision/OCR (sheet scan)
2. ☐ Parameter explainer (plain language)
3. ☐ Contextual explanation (summary)
4. ☐ Second opinion (BERT verification)
5. ☐ Smart interview (dynamic questions)
6. ☐ Trend analysis (Day 4)

**6/6** = judges will be impressed  
**4–5** = solid  
**<4** = too thin — judges may see "basic integration"

## Fallback
- Scan: if OCR is weak → prioritize PDF (cleaner than photos)
- Second opinion: skip if no time — not must-have
- PDF report: optional nice-to-have
- Never drop the parameter explainer — core feature
