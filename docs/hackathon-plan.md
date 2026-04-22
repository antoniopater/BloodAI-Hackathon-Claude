# BloodAI Triage + Specialist Finder — Hackathon Plan

## One-line concept (elevator pitch)
**"Scan a blood test printout → AI explains results in plain language → tells you which specialist to see → shows NFZ and private doctor queues with slots, ratings, and phone numbers."**

---

## Architecture

```
┌──────────────────── FRONTEND (React JSX) ──────────────────────────────┐
│                                                                         │
│  0. SCAN         1. INPUT         2. TRIAGE        3. FIND DOCTOR      │
│  ┌──────────┐   ┌───────────┐   ┌──────────────┐  ┌────────────────┐  │
│  │📷 Camera │   │ Manual or │   │ 8-class bars │  │ NFZ queues     │  │
│  │  or 📄   │──▶│ auto-fill │──▶│ + attention  │─▶│ + private      │  │
│  │ PDF/photo│   │ + explain │   │ + explanation│  │ map, slots     │  │
│  └──────────┘   │ + trends  │   │ + dual mode  │  │ phone, nav     │  │
│                  └───────────┘   └──────────────┘  └────────────────┘  │
│                  ↕ parameters    ↕ mode                               │
│              plain-language      patient / clinician                  │
│              explanations + ranges                                    │
│              from sheet or defaults                                   │
└───┬──────────────┬──────────────────┬──────────────┬──────────┬────────┘
    │              │                  │              │          │
┌───▼────┐    ┌────▼────┐      ┌─────▼─────┐  ┌────▼────┐ ┌───▼──────┐
│Opus 4.7│    │Opus 4.7 │      │ BERT Model│  │NFZ API  │ │Google    │
│ Vision │    │ Explain │      │ (FastAPI) │  │Treatment│ │Places API│
└────────┘    └─────────┘      └───────────┘  │Dates    │ └──────────┘
- Photo OCR   - Parameter      - Inference   └─────────┘  - Private
- Extract     explainer        - Attention    - Queues     - Ratings
  values +    plain language   - Probabilities- Slots       - Phone
  ranges      - Contextual                    - ~14k sites
  from sheet  explanations                    - Free public API
- PDF parse   - Trend analysis
```

### Key product features

**📷 Result scan (Camera/PDF):**
The user photographs a lab printout or uploads PDF. Opus 4.7 Vision:
1. Recognizes parameters and values (OCR)
2. Recognizes reference ranges from the same sheet (each lab uses its own ranges)
3. Auto-fills the form
4. If ranges are unreadable → fallback to defaults from lab_norms.json

**📖 Parameter explainer (plain language):**
For each parameter the user sees:
- What it is (e.g. "Creatinine — shows how well your kidneys filter blood")
- What their value means (e.g. "Your 4.8 is far above the reference range — kidneys may be struggling to filter")
- Opus 4.7 generates these dynamically using age, sex, and the full panel

**🔬 Combination context:**
Opus understands that low hemoglobin + high creatinine together is a different story than either alone — explanations reflect cross-parameter relationships

**👤/🩺 Dual mode — patient vs clinician:**
- **Patient mode**: simplified view, no raw probabilities, plain language, clear "consult a physician" disclaimer, color indicators (green/yellow/red)
- **Clinical mode**: full 8-class probabilities, attention heatmap, raw values, ECE confidence, dual-review option, printable PDF report
- UI toggle — same model, different presentation
- Mitigates "self-diagnosis" concern: patient mode never shows raw scores, only "we recommend a nephrology consult"

**📈 Time trends (compare results):**
- User can add 2+ result sets (e.g. March vs now)
- System shows ↑↓ arrows and simple trend visualization
- Opus interprets: "Creatinine rose from 1.8 to 4.8 in 3 months — rapid progression that warrants urgent nephrology follow-up"
- Competitors (TestResult.ai, Aima) lack this
- Clinicians care about trajectories — adds clinical credibility

**🏥 NFZ queues + private doctors:**
Beyond Google Places alone, integrate Poland's public NFZ "Treatment Dates" API:
- `https://api.nfz.gov.pl/app-itl-api/queues` — first free slot, average wait
- ~14,000 facilities, weekly updates
- After triage: "Nephrologist in Warsaw — NFZ: first slot in 47 days, private: ~3 days"
- Sort by wait time, distance, NFZ vs private
- Strong differentiator for the Polish market — rarely combined with triage

---

## Work plan — day by day

### Day 1: Monday 21.04 — Pipeline + Foundation
**Goal: Full ML pipeline from scratch + backend serving predictions**

- [ ] Prepare repo (GitHub, open source — required!)
- [ ] Email organizers: checkpoint question + open source after hackathon
- [ ] **ML Pipeline (from scratch — "New Work Only"):**
  - [ ] Preprocessing script: Synthea + MIMIC → hybrid corpus
  - [ ] Tokenizer: build vocab (~140 tokens), quantize lab values
  - [ ] MLM pre-training script (6 layers, 256 hidden, 8 heads)
  - [ ] Fine-tuning script (multi-label, cost-sensitive focal loss)
  - [ ] Run training overnight (GPU) — checkpoint ready in the morning
- [ ] FastAPI `/predict` — JSON lab values → 8 probabilities + attention
- [ ] `/lab_norms` — reference ranges (defaults + override from sheet)
- [ ] `/questions` — adaptive interview bank
- [ ] README.md — project description, setup, architecture

### Day 2: Tuesday 22.04 — Frontend core + Parameter explainer
**Goal: Working UI with input, parameter explanations, triage results**

- [ ] React: form for results (HGB, HCT, PLT, MCV, WBC, Creatinine, ALT, age, sex)
- [ ] **🆕 Parameter explainer (plain language):**
  - [ ] Each parameter: tooltip/panel "What is it?", "What does your value mean?"
  - [ ] Color coding: ✅ in range, ⚠️ out of range, 🚨 critical
  - [ ] Opus 4.7 dynamic copy using context (age, sex, combinations)
  - [ ] Cache explanations — avoid API on every value change
- [ ] Results UI: 8 colored probability bars
- [ ] Attention heatmap — which parameters drove the decision
- [ ] Adaptive interview: out-of-range value → question → answer affects prediction
- [ ] Animations: smooth step transitions

### Day 3: Wednesday 23.04 — Opus 4.7 + Scan (KEY DAY)
**Goal: Opus as intelligence layer — scan, explanations, second opinion**

- [ ] **📷 Camera/PDF scan — extract results:**
  - [ ] Photo upload (camera/gallery) or lab PDF
  - [ ] Opus 4.7 Vision → OCR → parameters + values
  - [ ] Read reference ranges from sheet (each lab differs!)
  - [ ] Auto-fill form from detections
  - [ ] Preview: "We recognized these values — review and confirm"
  - [ ] Fallback: unreadable ranges → defaults from lab_norms.json
  - [ ] Handle: skewed photo, low quality, partial occlusion
- [ ] **Patient explanations**: triage + attention → accessible summary
- [ ] **Smart interview**: Opus generates contextual follow-ups
- [ ] **"Second opinion"**: Opus checks BERT, flags disagreements
- [ ] **PDF report**: downloadable/printable summary for the physician

### Day 4: Thursday 24.04 — NFZ queues + Dual mode + UX polish
**Goal: NFZ API integration, patient/clinician modes, UX refinement**

- [ ] **🏥 NFZ "Treatment Dates" API (KILLER FEATURE):**
  - [ ] Integrate `https://api.nfz.gov.pl/app-itl-api/queues`
  - [ ] Map BERT specialties → NFZ benefit strings (e.g. Nephrology → "PORADNIA NEFROLOGICZNA")
  - [ ] Fetch: first slot, average wait, address, phone
  - [ ] Filter by voivodeship/city (user geolocation)
  - [ ] Comparison view: NFZ (slot + wait) vs private (Google Places + rating)
  - [ ] Sort: shortest wait, nearest, best rating
- [ ] **👤/🩺 Dual mode:**
  - [ ] Toggle: patient ↔ clinician
  - [ ] Patient: color signals, text without raw scores, disclaimer
  - [ ] Clinician: full probabilities, attention, ECE, report
- [ ] **📈 Time trends (basic):**
  - [ ] "Add earlier results" → second value set
  - [ ] ↑↓ arrows + delta per parameter
  - [ ] Opus interprets direction of change
- [ ] Map with pins (Leaflet) — NFZ + private
- [ ] Responsiveness (mobile-first)
- [ ] Edge cases: empty NFZ results, API errors, loading states

### Day 5: Friday 25.04 — Demo prep + wrap-up
**Goal: "Wow" demo, everything works live**

- [ ] End-to-end test: PDF upload → triage → explanation → find doctor — no stalls
- [ ] Demo script: 4 scenarios:
  1. **📷 Sheet scan**: photo lab slip → auto-fill → triage → doctor (WOW!)
  2. **Simple case**: man 60, high creatinine → parameter explainer → Nephrology → find nephrologist
  3. **Complex multi-label**: woman 70, anemia + kidney failure → 5 specialties → Opus explains interactions → map
  4. **PDF upload**: lab PDF → full automation with sheet reference ranges
- [ ] Record backup video (if live demo fails)
- [ ] Verify public repo, complete README, open-source license
- [ ] Prepare 2-min pitch:
  - Problem: "Patients get lab results they don't understand, don't know who to see, wait months for the wrong specialist"
  - Stat: "In Poland average specialist wait ~4 months. Endocrinology median — 190 days."
  - Solution: "BloodAI: from blood results to specialist decision in ~60 seconds"
  - Demo: live (sheet scan → explanation → triage → NFZ queues)
  - Tech: BERT multi-label (research paper) + Opus 4.7 (Vision, NLG, verification) + NFZ API
  - Differentiator: "Not another ChatGPT wrapper. A dedicated clinical model with validation, Opus as an intelligence layer, and live NFZ data."
  - Impact: time saved for patients, GPs, and the health system

### Day 6: Saturday 26.04 — Hackathon day
- [ ] Final tests
- [ ] Deploy (Vercel frontend + Railway/Render backend)
- [ ] Demo!

---

## Maximizing points per category

### Impact (30%) — "Who uses this?"
- **Patients**: don't wait for a GP visit to know where to go; understand results
- **GPs**: automatic pre-screening; dual mode gives a professional attention view
- **Health system**: faster routing → faster treatment → shorter queues
- **Numbers for the pitch**:
  - Average specialist wait: ~4.1 months (WHC Barometer 2022)
  - Endocrinology: 190 days median (NFZ 2023)
  - GP to TAVR surgery wait: ~12.3 months
  - ~5% of healthy people have "abnormal" labs — unnecessary panic
- **Unique value**: no existing app combines ML triage + plain-language explanation + live NFZ queue data

### Demo (25%) — "Does it impress live?"
- 📷 Phone photo of lab sheet = strongest "wow" — judge takes a photo and sees it work
- Parameter explainer — "ah, THAT'S why I need nephrology"
- Dual mode — same result as patient vs clinician
- Live NFZ — "nephrologist in Warsaw, NFZ: 47 days, private: ~3 days" with real data
- Animated flow: scan → auto-fill → thinking → results → NFZ/private
- Attention heatmap is visually compelling
- Trends: "drop March results, drop today's — watch creatinine climb"

### Opus 4.7 Use (20%) — "Creative AI use"
- NOT a chatbot — intelligence layer over ML
- **Vision/OCR**: sheet scan + lab-specific reference ranges
- **Medical explainer**: dynamic plain-language parameter text
- **Combination context**: HGB↓ + Creatinine↑ together
- **Trend analysis**: compares 2+ panels, interprets direction
- **Dual output**: different copy for patient vs clinician (same model, different prompts)
- Dynamic interview (not only rigid rules)
- "Second opinion" — Opus checks BERT, flags disagreement
- Unique: hybrid clinical model + multimodal LLM, not "another API wrapper"
- **Six Opus use cases**: Vision, NLG patient, NLG clinical, trends, interview, verification

### Depth & Execution (20%) — "Is it solid?"
- Research paper as foundation (peer-reviewed methodology)
- Patient-level validation, cost-sensitive loss
- Attention-based interpretability (XAI)
- Dual mode — thoughtful UX, not feature bloat
- Integration with public government API (NFZ) — real data, not mocks
- Trend analysis — clinically justified (clinicians track trajectories)
- Open source, clean code, documented API
- Error handling, edge cases, loading states, fallbacks at every step

---

## Risks and mitigation

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Model fails on new server | Medium | Test deployment on Day 1 |
| Google Places API limits | Low | Cache results, mock fallback |
| Opus API rate limits | Medium | Cache explanations, template fallback |
| Live demo stalls | Medium | Backup video, pre-loaded scenarios |
| Frontend looks weak | Low | shadcn/ui + small design system |
| OCR misreads sheet | Medium | "Review and confirm" screen, manual fallback |
| Sheet ranges misread | Medium | Fallback to lab_norms.json + validation |
| Camera API flaky in browser | Low | File upload fallback (photo/PDF) |
| NFZ API slow/down | Low | Cache data, last-good snapshot |
| Judges ask "how is this different from ChatGPT?" | High | Prepare clear answer (below) |

---

## Answer: "How is this different from pasting results into ChatGPT?"

Expect this question.

1. **Dedicated ML vs general LLM**: Our BERT is trained on clinical data (MIMIC + Synthea, 260k encounters) with cost-sensitive focal loss — measurable sensitivity (e.g. ER) and ECE calibration. ChatGPT has no clinical validation layer.

2. **Multi-label output**: eight calibrated probabilities at once. An LLM returns one narrative without calibrated multi-class scores.

3. **Interpretability**: attention shows WHY the model routed that way. ChatGPT is a black box.

4. **Opus does not replace the model**: it sits above — explains, verifies, analyzes trends. Hybrid, not monolith.

5. **Real operational data**: NFZ API returns actual queues, not generic "see a doctor" advice.

---

## Answer: "Isn't it dangerous — patients self-diagnosing?"

1. **Dual mode**: patient mode never shows raw probabilities — only "we recommend a nephrology consult", not "92% nephrology".

2. **Human-in-the-loop**: disclaimers on every screen. The system suggests; it does not diagnose.

3. **Better than status quo**: alternative is googling "high creatinine" and reading forums. Here: validated, calibrated routing suggestion.

4. **Clinician mode exists**: GPs can use the full view to support decisions.
