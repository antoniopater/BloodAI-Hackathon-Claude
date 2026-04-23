# Vision validation harness

Production-grade validation of Claude Opus 4.7 Vision OCR on Polish
morfologia (CBC) reports. Structured around a cache-first pytest harness so
you can iterate on prompt and normalizer code without burning API credits,
then do a single `--live` sweep before the demo to refresh the caches.

## Layout

```
tests/vision/
├── conftest.py                # --live / --prompt flags, opus_client, case loader
├── metrics.py                 # EMR, per-field P/R/F1, CER, ECE, unit-swap, p95 latency
├── test_normalizer.py         # ~85 offline unit tests for api.normalizer
├── test_metrics.py            # sanity tests for the metrics module
├── test_vision_harness.py     # parametrised end-to-end tests
├── compare_runs.py            # champion/challenger diff of two run logs
├── synthetic/                 # generator + seed fixtures (PNG + JSON)
├── golden/real/               # real anonymised lab scans (gitignored PHI)
├── regression/                # cases that once failed — pinned forever
└── runs/                      # append-only JSONL run logs from the /scan endpoint
```

## Running

```bash
# 1. Install dev deps once
pip install -r requirements-dev.txt

# 2. Generate synthetic fixtures (reproducible; commit the PNG + JSON pairs)
python tests/vision/synthetic/generate.py

# 3. Offline tests — zero API cost, CI-safe. Pytest plugin autoload is disabled
#    because the global env has a deepeval plugin that conflicts with langchain.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/vision -v

# 4. One live Opus sweep before the demo (refreshes cache; commit the result)
export ANTHROPIC_API_KEY=sk-ant-...
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/vision --live -v
git add tests/vision/**/*.cache.*.json tests/vision/runs/
git commit -m "vision: refresh Opus cache (prompt v1)"

# 5. Champion/challenger — compare two prompt versions
python -m pytest tests/vision --live --prompt=v2 -v
python tests/vision/compare_runs.py v1 v2
```

## Adding a test case

1. **Synthetic (preferred for failure-mode coverage):** add an entry to
   `_seed_cases()` in `synthetic/generate.py`, then re-run the generator. The
   generator emits a PNG + JSON pair; commit both.

2. **Golden (real anonymised):** drop a `.jpg` / `.png` / `.pdf` under
   `golden/real/` and write a sibling `.json` with the test-case schema
   below. **Strip PHI first** — see "Privacy" below.

3. **Regression:** when the `--live` run surfaces a failure on a real case,
   copy the image + refreshed cache into `regression/` so it never regresses
   silently.

### Test-case schema

```json
{
  "image": "seed_03_rotation_3deg.png",
  "lab_chain": "DIAGNOSTYKA",
  "layout": "single_column",
  "quality_tier": "mild_blur",
  "degradations": ["rotate_deg_3"],
  "patient": {"age": 33, "sex": "m"},
  "ground_truth_values": {"HGB": 14.2, "WBC": 6.8, "PLT": 230, "MCV": 88,
                          "CREATININE": 0.9, "ALT": 22, "AST": 19, "UREA": 15},
  "ground_truth_units":  {"HGB": "g/dL", ...},
  "ground_truth_ref_ranges": {"HGB": [12.0, 16.0], ...},
  "ground_truth_collected_at": "2026-03-05",
  "notes": "short description for failure triage"
}
```

## Acceptance criteria (hackathon)

On the frozen golden + synthetic set (caches committed):

| metric                          | threshold                      |
|---------------------------------|-------------------------------|
| EMR per-param fuzzy (HGB/WBC/PLT/MCV) | ≥ 0.90                    |
| EMR per-param fuzzy (others)    | ≥ 0.85                        |
| Per-field F1 (all 8 params)     | ≥ 0.88                        |
| Unit-swap FN rate               | < 1 %                         |
| ECE on numeric confidence       | < 0.10                        |
| CER on `rawText`                | < 0.05                        |
| p95 latency (`--live`)          | < 6 s                         |
| Cost / doc                      | < $0.05                       |
| End-to-end triage-class match   | ≥ 0.90                        |

Default `--live` cost budget on the 5 seeds + 10 real scans ≈ **$1.20**
(15 × ~$0.08).

## Privacy

- Real lab scans contain PHI. Strip patient name, PESEL, and DOB
  **before** committing — use Preview / GIMP to paint over those
  rectangles. The `notes` JSON field gets PESEL-shaped digit runs redacted
  automatically by `api.normalizer.strip_phi`, but image redaction is your
  job.
- Run logs under `runs/` are PHI-stripped before write — they never
  contain patient name / PESEL / DOB, only the image SHA-256 and the
  numeric extraction.
- Retention: 30 days on disk, rotated daily. In production you'd push the
  logs to S3 with KMS + 90-day lifecycle; that's deliberately out of scope
  for the hackathon.

## Known issues

- **Class code drift between backend and frontend.** The BERT backend
  emits Polish class codes (`SOR`, `HEMATO`, `NEFRO`, `CARDIO`, `PULMO`,
  `GASTRO`, `HEPATO`, `POZ`), while `frontend/src/types/medical.ts` uses
  English (`ER`, `Hematology`, `Nephrology`, …). The triage passthrough
  test in the harness maps via a local dict; full synchronisation is a
  separate ticket.
- **`anthropic==0.16.0`** in `requirements.txt` is Claude 3-era. The
  `/scan` endpoint assumes a newer SDK that supports `claude-opus-4-7`
  vision blocks. Before the `--live` sweep:
  `pip install -U anthropic`.
- **Synthetic renderer uses Pillow, not Playwright.** The original plan
  specified HTML → Playwright; we swapped it for Pillow to eliminate the
  chromium install. Visual fidelity is coarser (no logos, no signatures)
  but OCR-robustness characteristics (decimals, units, synonyms, blur,
  rotation) are fully exercised.
- **PDF multi-page** uses the first page only. `pdf2image` is listed in
  `requirements-dev.txt` as the fallback renderer when a PDF contains
  pages beyond page 1; the endpoint currently forwards the whole PDF via
  Anthropic's document block and lets the model choose.
- **No drift detector ships today.** The run log schema is ready for one
  (KS-test the confidence distribution against a baseline); if you need
  it, it's a ~50-line script over `runs/*.jsonl`.

## Reused from the rest of the repo

| existing                              | reuse                                            |
|----------------------------------------|--------------------------------------------------|
| `data.utils.load_lab_norms`            | `api.normalizer.fallback_ref_range`              |
| `data.utils.get_age_group`             | same                                              |
| `config/lab_norms.json`                | reference ranges for 8 params                    |
| `model.evaluate.compute_ece`           | mirrored (not imported) in `metrics.py` for light deps |
| `skills/day3-opus/SKILL.md` (l.22–53)  | lifted verbatim into `prompts/scan_v1.md`        |
| `frontend/src/types/api.ts::ScanResponse` | enforced by `api/scan.py::ScanResponseModel`  |
