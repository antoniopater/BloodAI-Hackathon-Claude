---
name: bloodai-day4-nfz-dualmode
description: "BloodAI hackathon Day 4: NFZ Treatment Dates API, dual mode (patient/clinician), time trends. Killer features that differentiate from competitors."
---

# Day 4: NFZ Queues + Dual Mode + Trends

## Goal for the day
By end of day: triage results wired to live NFZ queue data ("Nephrologist Warsaw — first appointment in 47 days"), patient/clinician toggle, and basic trend comparison.

## Task checklist

### Block 1: NFZ API Integration (3–4h) ⭐ KILLER FEATURE
- [ ] Map 8 BERT classes → NFZ service names:
```json
{
  "poz": "PORADNIA (GABINET) LEKARZA POZ",
  "gastro": "PORADNIA GASTROENTEROLOGICZNA",
  "hema": "PORADNIA HEMATOLOGICZNA",
  "neph": "PORADNIA NEFROLOGICZNA",
  "sor": null,
  "cardio": "PORADNIA KARDIOLOGICZNA",
  "pulmo": "PORADNIA CHORÓB PŁUC",
  "hepa": "PORADNIA HEPATOLOGICZNA"
}
```
(ER/SOR = no queue — show "Go to the nearest ER!")

- [ ] Backend endpoint `GET /nfz/queues`:
```python
@app.get("/nfz/queues")
async def get_nfz_queues(
    specialty: str,        # e.g. "PORADNIA NEFROLOGICZNA"
    province: str = "07",  # 07 = Mazowieckie
    locality: str = None   # e.g. "Warszawa"
):
    url = f"https://api.nfz.gov.pl/app-itl-api/queues"
    params = {
        "case": 1,
        "benefit": specialty,
        "province": province,
        "locality": locality or "",
        "format": "json",
        "limit": 10,
        "api-version": "1.3"
    }
    # Parse response → extract:
    # - provider (facility name)
    # - place (address)
    # - dates.date (first available slot)
    # - statistics.provider-data.awaiting (waiting count)
    # - statistics.provider-data.average-period (avg wait in days)
    # - phone
```

- [ ] Frontend: "Find a specialist" section after triage
  - For each flagged specialty (prob > threshold):
    - Card with NFZ data: facility name, address, first slot, wait time, phone
    - Badge: "NFZ" (green) vs "Private" (blue)
    - Sort: by soonest slot, by distance, by queue length
  - If ER flagged: large red banner "Seek emergency care or call emergency services immediately"
  - "Call" (`tel:` link), "Navigate" (Google Maps link)

- [ ] Geolocation:
  - `navigator.geolocation` → infer voivodeship/city
  - Fallback: voivodeship dropdown
  - Map location → NFZ province code (01–16)

- [ ] Map (Leaflet):
  - Pins for NFZ facilities
  - Popup: name, slot, wait, phone
  - Pin color: green (short wait) → red (long wait)

- [ ] Cache NFZ responses ~1h (don't hammer the API)

### Block 2: Dual Mode — Patient / Clinician (2h)
- [ ] Header toggle: 👤 Patient ↔ 🩺 Clinician
- [ ] State in React context/state

**Patient mode:**
- [ ] Triage display: instead of "Nephrology: 92%" → "We recommend a nephrology consult" (🔴🟡🟢 indicator)
- [ ] No raw probabilities, no attention scores
- [ ] Opus explanations: patient-oriented plain language
- [ ] Visible disclaimer: "This tool supports care; it does not replace a doctor"
- [ ] NFZ section: focus on "when can I get seen"

**Clinician mode:**
- [ ] Full 8-class probabilities with threshold markers
- [ ] Attention heatmap with scores
- [ ] ECE confidence (if available)
- [ ] Opus explanations: clinical terminology
- [ ] "Dual review" option when >1 specialty > 0.5
- [ ] "Generate report" (printable)

### Block 3: Time Trends — basic (1–2h)
- [ ] Button "Compare with previous results"
- [ ] Second form (or second scan upload)
- [ ] Comparison table:
```
Parameter   | Previous  | Current   | Change | Trend
Creatinine  | 1.8 mg/dL | 4.8 mg/dL | +3.0   | ⬆️⬆️ (rapid rise)
HGB         | 13.5 g/dL | 12.0 g/dL | -1.5   | ⬇️ (decline)
```
- [ ] Opus 4.7 trend interpretation:
```
Prompt:
"Patient {age}, {sex}. Result comparison:
{change table}
Period: {date1} → {date2}

Interpret clinical meaning of trends (max 100 words).
Which changes are concerning? Is the rate of change significant?"
```

### Block 4: UX polish + Edge Cases (1h)
- [ ] Loading states for NFZ API (can be slow)
- [ ] Error handling: NFZ down → "Queue data temporarily unavailable, try again shortly"
- [ ] Empty state: no results nearby → "No results. Try widening the search area."
- [ ] Mobile responsive pass

## End-of-day self-assessment

| Question | Score |
|----------|-------|
| Do NFZ queues show real slots from the API? | /5 |
| Does dual mode switch views sensibly? | /5 |
| Does patient mode hide raw numbers? | /5 |
| Are trends readable and interpreted by Opus? | /5 |
| Does full flow scan→triage→explain→NFZ work end-to-end? | /5 |

**25/25** = tomorrow only polish and demo prep  
**20–24** = solid; morning fixes + demo  
**15–19** = NFZ and dual mode MUST work — trends optional  
**<15** = simplify: NFZ first, dual mode second, trends last

## NFZ API — technical notes
- API is public, no API key
- Rate limit: none documented — be polite (cache!)
- Paginated responses (25/page), use `limit=10`
- Data updated by facilities on business days
- `case` param: 1=stable, 2=urgent — use 1 for normal triage
- Province codes: 01–16 (07=Mazowieckie, 06=Lubelskie, etc.)
