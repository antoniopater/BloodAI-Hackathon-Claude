# BloodAI — Vision OCR Layer (Opus 4.7)

Complete documentation for the scan-image-to-structured-values pipeline: architecture, integration, testing, prompt versioning, and how to extend it.

---

## Table of contents

1. [What this layer does](#1-what-this-layer-does)
2. [Architecture overview](#2-architecture-overview)
3. [Request flow (step by step)](#3-request-flow-step-by-step)
4. [API contract — POST /scan](#4-api-contract--post-scan)
5. [Prompt system](#5-prompt-system)
6. [Normalizer — api/normalizer.py](#6-normalizer--apinormalizerpy)
7. [PHI stripping](#7-phi-stripping)
8. [Frontend integration](#8-frontend-integration)
9. [Validation harness](#9-validation-harness)
10. [Test datasets](#10-test-datasets)
11. [Metrics](#11-metrics)
12. [Champion/challenger workflow](#12-championchallenger-workflow)
13. [Configuration and environment variables](#13-configuration-and-environment-variables)
14. [Cost model](#14-cost-model)
15. [Known limitations](#15-known-limitations)

---

## 1. What this layer does

The user photographs (or uploads a PDF of) a blood-test result sheet. The Vision OCR layer:

- Decodes the image/PDF from the browser's `data:` URL
- Sends it to **Claude Opus 4.7 Vision** with a versioned system prompt
- Parses and normalises the raw JSON the model returns (decimal separators, unit variants, name synonyms, PHI)
- Returns a typed `ScanResponse` that the frontend and the ML triage model can consume directly

The layer deliberately does **not** interpret clinical significance — that is the job of the ML triage model (`POST /predict`) and the Opus explanation route (`POST /explain`).

---

## 2. Architecture overview

```
Browser (React)
│  imageDataUrl (base64 data: URL, PNG / JPEG / PDF)
│  + optional hint, age, sex
▼
POST /scan   ──────────────────────────────────────────────────────────
api/scan.py                                                            │
│  _decode_data_url()   → bytes + MIME type                           │
│  _load_prompt("v1")   → prompts/scan_v1.md                         │
│  _parse_with_retry()  → one call, one decimal-sep retry             │
│      └─ _call_opus_vision()  ─── Claude Opus 4.7 Vision ───────────┘
│  normalize_opus_response()  → api/normalizer.py
│  strip_phi()                → PHI-safe log record
│  _log_run()                 → tests/vision/runs/<date>.jsonl
▼
ScanResponseModel  { values, confidence, rawText, collectedAt }
│
├── frontend renders parameter table + flags out-of-range values
└── POST /predict  ← values dict forwarded to ML triage model
```

**Key files:**

| File | Role |
|------|------|
| `api/scan.py` | FastAPI router, orchestration, retry, run logging |
| `api/normalizer.py` | Pure-function normalizer (no I/O, fully unit-tested) |
| `prompts/scan_v1.md` | Versioned OCR system prompt |
| `config/lab_norms.json` | Reference ranges DB (fallback when sheet is missing them) |
| `tests/vision/conftest.py` | Cache-first pytest fixtures (`OpusClient`, `Case`) |
| `tests/vision/metrics.py` | EMR, P/R/F1, CER, ECE, unit_swap_rate, latency_p95 |
| `tests/vision/test_vision_harness.py` | 21 parametrised end-to-end tests |
| `tests/vision/compare_runs.py` | Champion/challenger CLI |

---

## 3. Request flow (step by step)

```
1. Browser → POST /scan
   body: { imageDataUrl: "data:image/png;base64,...", age: 45, sex: "m" }

2. _decode_data_url()
   → strips prefix, base64-decodes, returns (bytes, "image/png")

3. _load_prompt("v1")
   → reads prompts/scan_v1.md, strips the Markdown header above "---"

4. _call_opus_vision(bytes, mime, prompt)
   → builds content block:
       image  → {"type":"image",  "source":{"type":"base64",...}}
       PDF    → {"type":"document","source":{"type":"base64",...}}
   → client.messages.create(model="claude-opus-4-7", max_tokens=4096, ...)
   → returns (raw_text_string, latency_ms, cost_usd_estimate)

5. json.loads(raw_text_string)  — first attempt

6. _looks_non_numeric(parsed)?
   If the model returned garbage or >50% of values can't be parsed as numbers:
   → retry with added clarification about Polish comma decimal separator
   → json.loads() again; raise HTTP 502 if still invalid

7. normalize_opus_response(parsed, age, sex, lab_norms)
   → canonicalize_name():   "Hemoglobina" → "HGB", "Leukocyty" → "WBC", …
   → parse_number_pl():     "14,2" → 14.2, "1 234,5" → 1234.5
   → convert_unit():        g/L → g/dL (÷10), /cumm → K/uL (÷1000 if >500), …
   → returns { values: {HGB:14.2, WBC:6.22, …}, confidence: {…},
               rawText: …, collectedAt: "2025-04-28" }

8. strip_phi(parsed)  → removes name/PESEL/address before logging

9. _log_run()  → appends one JSON line to tests/vision/runs/<UTC-date>.jsonl

10. Return ScanResponseModel to browser
```

---

## 4. API contract — POST /scan

### Request

```typescript
// frontend/src/types/api.ts
interface ScanRequest {
  imageDataUrl: string;   // data:image/png;base64,… or data:application/pdf;base64,…
  hint?:        string;   // free-text hint to the model (rarely used)
  age?:         number;   // used for fallback reference ranges
  sex?:         string;   // "m" | "f"
}
```

Supported MIME types: `image/png`, `image/jpeg`, `image/webp`, `application/pdf`.

### Response

```typescript
interface ScanResponse {
  values:       Partial<Record<LabParam, number>>;  // canonical float values
  confidence:   Partial<Record<LabParam, number>>;  // 0.3 | 0.6 | 0.9
  rawText?:     string;                             // Opus rawText field if present
  collectedAt?: string;                             // ISO date "YYYY-MM-DD"
}

type LabParam = "HGB" | "WBC" | "PLT" | "MCV" | "CREATININE" | "ALT" | "AST" | "UREA";
```

### Error codes

| Code | Meaning |
|------|---------|
| 400 | Invalid data URL or empty payload |
| 502 | Opus returned non-JSON after retry |
| 503 | `anthropic` SDK not installed or `ANTHROPIC_API_KEY` missing |

---

## 5. Prompt system

### Location and versioning

```
prompts/
└── scan_v1.md       ← active prompt (version "v1")
    scan_v2.md       ← future challenger (not yet created)
```

The file is a Markdown document. Everything **above** the first `---` separator is a human-readable header; everything below is the actual prompt text sent to the model. `_load_prompt(version)` strips the header automatically.

### What the prompt instructs Opus to extract

1. Each lab parameter: `name`, `value`, `unit` (numeric, not string)
2. Reference ranges from the sheet (if visible)
3. Patient metadata: `age`, `sex` — **no name, PESEL, address**
4. Lab name and collection date

### Output schema the prompt enforces

```json
{
  "patient": {"age": 45, "sex": "m"},
  "lab_name": "Diagnostyka",
  "collected_at": "2025-04-28",
  "parameters": [
    {
      "name": "HGB",
      "value": 14.2,
      "unit": "g/dL",
      "reference_low": 12.0,
      "reference_high": 17.5,
      "source": "from_sheet",
      "confidence": "high"
    }
  ],
  "confidence": "high",
  "notes": "…"
}
```

### Polish-specific prompt rules

- Comma is the decimal separator in Polish: `14,2` → emit `14.2` (float)
- Unit equivalences: `10³/µL = tys./µL = K/uL`
- Synonym table: `Hemoglobina = HGB`, `Leukocyty = WBC`, `Płytki/Trombocyty = PLT`, `Kreatynina = CREATININE`, `Mocznik = UREA`, `ALAT = ALT`, `ASPAT = AST`

### How to iterate on the prompt

Never edit `scan_v1.md` in place — create `scan_v2.md` and run champion/challenger:

```bash
# Populate v2 caches without overwriting v1 caches
pytest tests/vision --live --prompt=v2

# Compare accuracy and cost
python tests/vision/compare_runs.py v1 v2
```

---

## 6. Normalizer — api/normalizer.py

Fully deterministic, side-effect-free. All functions are unit-tested in `tests/vision/test_normalizer.py` (~85 tests, run in 0.09 s offline).

### Canonical parameter set

```python
CANONICAL = ("HGB", "CREATININE", "PLT", "MCV", "WBC", "ALT", "AST", "UREA")
```

### Canonical units

| Parameter | Canonical unit | Notes |
|-----------|---------------|-------|
| HGB | g/dL | g/L → ÷10; mmol/L → ×1.611 |
| WBC | K/uL | 10⁹/L → same value; /cumm or /µL → ÷1000 when value >500 |
| PLT | K/uL | same conversions as WBC |
| MCV | fL | µm³ is identical (1 fL = 1 µm³) |
| CREATININE | mg/dL | µmol/L → ÷88.4 |
| ALT | U/L | — |
| AST | U/L | — |
| UREA | mg/dL | mmol/L → ×2.801 (BUN convention) |

### Key functions

#### `parse_number_pl(raw) → float | None`

Accepts Polish decimal format, thousands with spaces, inequality prefixes:
- `"14,2"` → `14.2`
- `"1 234,5"` → `1234.5`
- `"<5"` → `5.0` (inequality stripped; caller treats it as the threshold)
- `">4"` → `4.0`
- Already-numeric types pass through
- Returns `None` for booleans, NaN, unparseable strings

#### `canonicalize_name(raw) → str | None`

Case-insensitive synonym lookup covering Polish and English names. Returns the canonical uppercase code (`"HGB"`, `"WBC"`, …) or `None` for unknown parameters (unknown params are silently dropped — the frontend stays functional with a partial result set).

#### `convert_unit(param, value, unit) → (float, str)`

Converts `(value, unit)` to the canonical unit. Returns `(converted_value, canonical_unit_string)`.

**Critical edge case — Indian labs (`/cumm`, `/µL`):**
Indian laboratory systems print WBC and PLT in cells/µL (absolute counts), e.g. `WBC = 6220 /cumm`. Polish labs use K/uL (`6.22`). The normalizer detects `value > 500` and divides by 1000:

```python
if u in ("/cumm", "/ul", "cells/ul", "cells/cumm", "cells/microl", "/microl"):
    if value > 500:
        return value / 1000.0, "K/uL"
```

This threshold (`> 500`) is safe because no physiologically plausible K/uL WBC or PLT value exceeds 500 in normal or critical ranges.

#### `parse_ref_range(raw) → (low, high)`

Accepts `"80-100"`, `"80–100"` (en dash), `"80 do 100"`, `"<100"`, `">4"`, or a `[low, high]` list.

#### `fallback_ref_range(param, age, sex, norms_db) → (low, high)`

Called by the endpoint when the OCR couldn't read reference ranges from the sheet. Looks up `config/lab_norms.json` with age-group and sex bucketing. Falls back to adult/female if either is unknown.

#### `normalize_opus_response(raw, age, sex, norms_db) → ScanResponse`

Top-level entry point. Orchestrates: iterate `parameters[]` → canonicalize name → parse value → convert unit → collect confidence. Defensive: malformed entries are skipped, unknown names dropped. Never raises.

---

## 7. PHI stripping

`strip_phi(raw_json)` removes patient-identifying fields before the run record is written to disk:

- **Top-level keys** matching `_PHI_KEYS` (name, PESEL, dob, address, phone, email, and Polish/variant spellings) are dropped
- **Under `patient`**: same key set
- **String values** containing 9–13 consecutive digits (PESEL-like) are replaced with `[REDACTED]`
- The `parameters[].name` field is **not** touched (it's a lab parameter name like `"HGB"`, not a person name)

PHI stripping applies only to **logged records** (`tests/vision/runs/*.jsonl`). The API response returned to the frontend does not carry patient name or PESEL in the first place (the prompt instructs Opus to omit them, and the normalizer discards non-canonical fields).

---

## 8. Frontend integration

### Where the call is initiated

`frontend/src/components/UI/CameraCapture.tsx` — the user either takes a photo via `getUserMedia` (with front/back camera toggle) or uploads a file. The component produces a `data:` URL and calls the `/scan` endpoint.

### Data flow after scan

```
CameraCapture → POST /scan → ScanResponse
    ↓
ResultsScreen:
  values dict   → parameter table with reference ranges + colour flags
  confidence    → uncertainty badge per value
  collectedAt   → date label
    ↓
POST /predict (values dict forwarded) → triage probabilities
    ↓
POST /explain (values + triage) → Opus narrative explanation
```

### Type alignment

The TypeScript type `ScanResponse` at `frontend/src/types/api.ts` mirrors `ScanResponseModel` in `api/scan.py` — both sides use the same canonical param codes as keys.

---

## 9. Validation harness

### Philosophy

The test suite is **cache-first**: by default it reads committed `.cache.v1.json` files (zero API calls, runs in ~0.09 s). The `--live` flag hits the real Opus API and refreshes the cache. This means:

- CI never burns API credits
- A single `--live` run pays once and the result is committed; all subsequent runs are free
- Different prompt versions get isolated cache files (`*.cache.v2.json`) so champion and challenger never overwrite each other

### Running the suite

```bash
# Offline (cached responses, zero cost, fast)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/vision -v

# Live sweep (calls Opus, refreshes caches)
export ANTHROPIC_API_KEY=sk-ant-...
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/vision --live -v

# Live sweep for a specific subset only
python -m pytest tests/vision --live -k "seed_06 or scan_003" -v

# Test a new prompt version (isolated cache)
python -m pytest tests/vision --live --prompt=v2 -v
```

### Test structure

```
tests/vision/
├── conftest.py              Case discovery + OpusClient fixture
├── metrics.py               Metric functions (offline, numpy only)
├── test_normalizer.py       ~85 unit tests for api/normalizer.py
├── test_metrics.py          Sanity tests for metric functions
├── test_vision_harness.py   21 parametrised end-to-end tests
│   ├── test_extraction_meets_tolerance[seed_01..seed_09]   (9 synthetic)
│   ├── test_extraction_meets_tolerance[scan_001..scan_009] (9 real scans)
│   ├── test_aggregate_unit_swap_rate_below_threshold
│   ├── test_aggregate_exact_match_rate_above_threshold
│   └── test_minimum_synthetic_seeds_present
├── test_scan_endpoint.py    Integration tests for POST /scan (mocked Opus)
└── compare_runs.py          Champion/challenger CLI
```

### Aggregate thresholds

| Metric | Threshold | Current result |
|--------|-----------|---------------|
| Mean exact match rate (EMR) | ≥ 0.85 | 1.00 (all 21 cached) |
| Unit swap rate | < 0.01 | 0.00 |

---

## 10. Test datasets

### Synthetic seeds (`tests/vision/synthetic/`)

Generated by `tests/vision/synthetic/generate.py`. Each seed is a PNG image plus a JSON ground truth sidecar.

| Seed | Degradation | What it tests |
|------|-------------|--------------|
| `seed_01_decimal_comma` | none (clean) | baseline Polish comma separator |
| `seed_02_unit_swap_hgb_gL` | none (clean) | HGB printed in g/L → normalizer ÷10 |
| `seed_03_rotation_3deg` | `rotate_deg_3` | slight scan tilt |
| `seed_04_blur_sigma2` | `gaussian_blur_sigma_2` | out-of-focus photo |
| `seed_05_two_column` | none (clean) | two-column layout (Diagnostyka style) |
| `seed_06_glare` | `glare + jpeg_q_75` | flash reflection obscuring text |
| `seed_07_handwritten_correction` | `handwritten_correction` | pen annotation over WBC row |
| `seed_08_cropped_bottom` | `crop_bottom` | bottom 30% missing — `collectedAt` must be null |
| `seed_09_wbc_unit_swap` | none (clean) | WBC=6800 /µL → normalizer → 6.8 K/uL |

Regenerate all seeds (if the generator or lab-sheet template changes):
```bash
python tests/vision/synthetic/generate.py
```

### Real scans (`tests/vision/golden/real/`)

9 anonymised PNG scans from the public Kaggle "Bajaj" dataset (Indian hospital PDFs — Shree Diagnostic, AIG Hospitals, Diagnostic Point). Patient names were removed from filenames; lab values were double-checked against Opus OCR output.

| Scan | Lab chain | Panel | Notable |
|------|-----------|-------|---------|
| `scan_001` | SHREE_DIAGNOSTIC | CBC | PLT=125 low; WBC in /cumm (÷1000) |
| `scan_002` | SHREE_DIAGNOSTIC | CBC + LFT | ALT=35, AST=30 |
| `scan_003` | SHREE_DIAGNOSTIC | CBC | PLT=398 (was 390 in manual annotation — OCR was right) |
| `scan_004` | DIAGNOSTIC_POINT | Creatinine | single value CREATININE=0.9 mg/dL |
| `scan_005` | AIG_HOSPITALS | CBC partial | HGB + WBC visible |
| `scan_006` | AIG_HOSPITALS | CBC partial | PLT only (HGB on different page) |
| `scan_007` | SHREE_DIAGNOSTIC | CBC | ⚠ patient name visible in image — redact before production use |
| `scan_008` | SHREE_DIAGNOSTIC | LFT | ALT=35, AST=30 |
| `scan_009` | DIAGNOSTIC_POINT | CBC | HGB=10.5 low |

**PHI note:** `scan_007.png` has a patient name handwritten in the image. The filename is anonymised but the pixel content is not. Redact with image editing before committing to a public fork.

---

## 11. Metrics

All metric functions live in `tests/vision/metrics.py`.

### Per-document

| Metric | Function | Description |
|--------|----------|-------------|
| Exact Match Rate (EMR) | `exact_match_rate(pred, gt)` | Fraction of GT fields matched within tolerance |
| Fuzzy match | `fuzzy_match(pred, gt)` | Per-param boolean dict |

### Per-corpus

| Metric | Function | Description |
|--------|----------|-------------|
| Precision / Recall / F1 | `per_field_prf1(preds, gts)` | Per-parameter across all documents |
| CER | `cer(pred_text, gt_text)` | Character error rate (needs ground-truth raw text) |
| ECE | `ece(confidences, correct)` | Calibration error of the model's confidence scores |
| Unit swap rate | `unit_swap_rate(preds, gts)` | Fraction of values ×10 or ÷10 off GT — detects unit confusion |
| Latency p95 | `latency_p95(latencies_ms)` | 95th percentile API latency |

### Tolerances

Absolute error allowed per parameter:

| HGB | WBC | PLT | MCV | CREATININE | ALT | AST | UREA |
|-----|-----|-----|-----|-----------|-----|-----|------|
| 0.1 g/dL | 0.1 K/uL | 5.0 K/uL | 1.0 fL | 0.05 mg/dL | 2.0 U/L | 2.0 U/L | 1.0 mg/dL |

Tolerance rationale: HGB ±0.1 is well within the analytical CV of 1%; PLT ±5 covers rounding from cells/cumm integer division.

### Run logs

Every live API call appends one JSON line to `tests/vision/runs/<UTC-date>.jsonl`. The `summarize(path)` function aggregates a run file into all metrics above.

---

## 12. Champion/challenger workflow

Used to evaluate a new prompt version before shipping it.

```bash
# Step 1: populate v1 caches (or they already exist from prior --live run)
python -m pytest tests/vision --live --prompt=v1 -v

# Step 2: write scan_v2.md (new prompt variant)
cp prompts/scan_v1.md prompts/scan_v2.md
# … edit scan_v2.md …

# Step 3: populate v2 caches (isolated — never touches v1 cache files)
python -m pytest tests/vision --live --prompt=v2 -v

# Step 4: compare
python tests/vision/compare_runs.py v1 v2
```

Example output:

```
Champion:   prompt=v1  file=2026-04-23.jsonl
Challenger: prompt=v2  file=2026-04-23.jsonl

metric              v1        v2        Δ
------------------  --------  --------  --------
calls               14        14        0
exact_match_rate    1.0000    0.9500    -0.0500
unit_swap_rate      0.0000    0.0000    0.0000
ece                 0.0000    0.0120    0.0120
latency_p95_ms      3200      2950      -250.0
total_cost_usd      0.0420    0.0390    -0.003

Per-field F1:
param               v1        v2        Δ
------------------  --------  --------  --------
HGB                 1.0000    1.0000    0.0000
PLT                 1.0000    0.9000    -0.1000
…
```

Promote `v2` → replace `scan_v1.md` only when EMR ≥ champion AND cost is equal or lower.

---

## 13. Configuration and environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | _(required for live calls)_ | Anthropic API key |
| `BLOODAI_MODEL_ID` | `claude-opus-4-7` | Model used for `/scan` calls |
| `BLOODAI_PROMPT_VERSION` | `v1` | Which `prompts/scan_<v>.md` to load |

Set in `.env` or export before starting uvicorn:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export BLOODAI_MODEL_ID=claude-opus-4-7
uvicorn api.main:app --reload
```

### max_tokens

Hard-coded to **4096** in `api/scan.py`. Do not reduce:
- A full CBC with differential (20+ parameters) can produce ~1800 output tokens
- At 2000 the response was truncated mid-JSON for multi-page Indian lab reports
- At 4096 all observed reports complete with room to spare

---

## 14. Cost model

Rough estimates based on Anthropic pricing at time of writing. Update the constants in `api/scan.py` when pricing changes.

```python
_COST_PER_MTOK_IN  = 15.0   # USD per million input tokens
_COST_PER_MTOK_OUT = 75.0   # USD per million output tokens
```

Typical single scan (image + CBC prompt + full JSON response):

| Token type | Approx. tokens | Cost |
|-----------|---------------|------|
| Input (image + prompt) | ~1200–2500 | $0.018–0.038 |
| Output (JSON response) | ~800–1800 | $0.060–0.135 |
| **Total per scan** | | **~$0.08–0.17** |

Retry (triggered by non-numeric output): doubles the cost. The retry is rare in practice (~3% of real-world images in testing).

Logged under `cost_estimate_usd` in each run record. Use `summarize()` to aggregate.

---

## 15. Known limitations

| Limitation | Workaround / status |
|------------|---------------------|
| `scan_007.png` has a visible patient name in the image pixel content | Redact with Preview → Markup before production use |
| Backend triage class codes are Polish (`SOR/HEMATO/…`); frontend expects English (`ER/Hematology/…`) | Tracked as a separate ticket; does not affect the Vision OCR layer |
| UREA not present in any of the 9 Kaggle real scans | Tested only via synthetic seed (Diagnostyka style); add a real UREA scan when available |
| No ground-truth `rawText` for real scans → CER cannot be computed for them | CER reported only on synthetic seeds where the text is known |
| The `/cumm` → K/uL threshold (`value > 500`) would misfire for a genuinely high platelet value printed as, say, `600000 /cumm` | This would divide to 600.0 K/uL, which is then flagged as thrombocytosis — clinically correct behaviour even if the intermediate step looks odd |
| PDFs with multiple pages: Opus sees all pages but the OCR prompt does not guide page selection | For multi-section reports (e.g. AIG where HGB and CBC counts are on different pages) some parameters may appear on a non-visible section |
