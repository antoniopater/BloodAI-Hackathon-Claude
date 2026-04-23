"""Synthetic Polish morfologia lab-sheet generator.

The plan called for Playwright-rendered HTML templates; this implementation
uses Pillow directly so the harness runs with zero chromium / node install.
Layout fidelity is intentionally modest — the goal is to stress-test the
OCR's handling of decimals, unit notations, synonyms, and image
degradations, not to reproduce photographic sheet layouts.

Each "fixture" is a pair of sibling files:
    seed_01_foo.png
    seed_01_foo.json    # test-case schema (see tests/vision/README.md)

Run:
    python tests/vision/synthetic/generate.py --seed 5
"""
from __future__ import annotations

import argparse
import io
import json
import random
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Pillow font loading — use the default bitmap font so the generator works
# without any system-font dependency. Larger sizes are obtained by tiling
# the default font (crude but deterministic).
# ---------------------------------------------------------------------------

def _load_font(size: int = 18) -> ImageFont.ImageFont:
    """Return a PIL ImageFont. Falls back to default if no TTF is available."""
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",           # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",        # Linux
        "/System/Library/Fonts/Helvetica.ttc",                    # macOS
        "C:\\Windows\\Fonts\\arial.ttf",                          # Windows
    ]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Spec types
# ---------------------------------------------------------------------------

@dataclass
class LabRow:
    printed_name: str                      # how it appears on the sheet (PL / EN)
    canonical: str                          # canonical LabParam code
    value_str: str                          # as printed, e.g. "14,2"
    value_number: float                     # ground-truth numeric
    unit: str                               # as printed
    ref_range: str                          # as printed, e.g. "12,0 - 16,0"


@dataclass
class LabSheetSpec:
    lab_chain: str
    patient_age: int
    patient_sex: str                        # "m" or "f"
    collected_at: str                       # ISO date string
    rows: List[LabRow]
    layout: str = "single_column"
    title: str = "Badanie morfologii krwi"


# ---------------------------------------------------------------------------
# Layout renderers
# ---------------------------------------------------------------------------

def _render_single_column(spec: LabSheetSpec) -> Image.Image:
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    title_font = _load_font(32)
    h_font = _load_font(18)
    body_font = _load_font(20)
    small_font = _load_font(14)

    # Header
    draw.text((40, 40), spec.lab_chain, font=title_font, fill="black")
    draw.text((40, 80), spec.title, font=h_font, fill="black")
    draw.text(
        (40, 110),
        f"Pacjent: wiek {spec.patient_age}, płeć {'M' if spec.patient_sex == 'm' else 'K'}",
        font=small_font,
        fill="black",
    )
    draw.text((40, 130), f"Data pobrania: {spec.collected_at}", font=small_font, fill="black")
    draw.line((40, 160, W - 40, 160), fill="black", width=2)

    # Column headers
    draw.text((40, 180), "Parametr", font=h_font, fill="black")
    draw.text((380, 180), "Wynik", font=h_font, fill="black")
    draw.text((540, 180), "Jednostka", font=h_font, fill="black")
    draw.text((700, 180), "Zakres", font=h_font, fill="black")
    draw.line((40, 210, W - 40, 210), fill="gray", width=1)

    y = 230
    for row in spec.rows:
        draw.text((40, y), row.printed_name, font=body_font, fill="black")
        draw.text((380, y), row.value_str, font=body_font, fill="black")
        draw.text((540, y), row.unit, font=body_font, fill="black")
        draw.text((700, y), row.ref_range, font=body_font, fill="black")
        y += 36

    draw.text((40, y + 20), "Wydruk elektroniczny — nie wymaga podpisu.", font=small_font, fill="gray")
    return img


def _render_two_column(spec: LabSheetSpec) -> Image.Image:
    W, H = 1100, 900
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    title_font = _load_font(26)
    h_font = _load_font(16)
    body_font = _load_font(18)
    small_font = _load_font(12)

    draw.text((40, 30), spec.lab_chain, font=title_font, fill="black")
    draw.text((40, 66), spec.title, font=h_font, fill="black")
    draw.text(
        (40, 90),
        f"Wiek {spec.patient_age} lat | Płeć: {'Mężczyzna' if spec.patient_sex == 'm' else 'Kobieta'} | Pobrano: {spec.collected_at}",
        font=small_font,
        fill="black",
    )
    draw.line((40, 120, W - 40, 120), fill="black", width=2)

    def _render_column(rows: List[LabRow], x0: int, y0: int) -> None:
        draw.text((x0, y0), "Parametr", font=h_font, fill="black")
        draw.text((x0 + 200, y0), "Wynik", font=h_font, fill="black")
        draw.text((x0 + 320, y0), "Norma", font=h_font, fill="black")
        draw.line((x0, y0 + 22, x0 + 480, y0 + 22), fill="gray", width=1)
        y = y0 + 34
        for row in rows:
            draw.text((x0, y), row.printed_name, font=body_font, fill="black")
            draw.text(
                (x0 + 200, y),
                f"{row.value_str} {row.unit}",
                font=body_font,
                fill="black",
            )
            draw.text((x0 + 320, y), row.ref_range, font=body_font, fill="black")
            y += 30

    mid = (len(spec.rows) + 1) // 2
    _render_column(spec.rows[:mid], 40, 140)
    _render_column(spec.rows[mid:], 560, 140)

    draw.text(
        (40, H - 40),
        "Wyniki orientacyjne — konsultacja lekarska wskazana.",
        font=small_font,
        fill="gray",
    )
    return img


LAYOUTS: Dict[str, Callable[[LabSheetSpec], Image.Image]] = {
    "single_column": _render_single_column,
    "two_column": _render_two_column,
}


# ---------------------------------------------------------------------------
# Augmentations
# ---------------------------------------------------------------------------

def augment(img: Image.Image, ops: List[str]) -> Image.Image:
    """Apply a list of augmentation operations in order.

    Each op is a string key from this set:
        gaussian_blur_sigma_N     - N integer (pixels)
        rotate_deg_N              - positive or negative degrees
        jpeg_q_N                  - re-encode with JPEG quality N
        glare                     - soft white blob in the upper half
        handwritten_correction    - scribble over a random line
    Unknown ops are ignored.
    """
    out = img.convert("RGB")
    for op in ops:
        if op.startswith("gaussian_blur_sigma_"):
            sigma = float(op.rsplit("_", 1)[-1])
            out = out.filter(ImageFilter.GaussianBlur(radius=sigma))
        elif op.startswith("rotate_deg_"):
            deg = float(op.rsplit("_", 1)[-1])
            out = out.rotate(deg, expand=True, fillcolor="white")
        elif op.startswith("jpeg_q_"):
            q = int(op.rsplit("_", 1)[-1])
            buf = io.BytesIO()
            out.save(buf, format="JPEG", quality=q)
            buf.seek(0)
            out = Image.open(buf).convert("RGB")
        elif op == "glare":
            overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)
            cx, cy = out.size[0] // 2, out.size[1] // 3
            for radius, alpha in [(260, 160), (180, 110), (110, 70)]:
                d.ellipse(
                    (cx - radius, cy - radius, cx + radius, cy + radius),
                    fill=(255, 255, 255, alpha),
                )
            out = Image.alpha_composite(out.convert("RGBA"), overlay).convert("RGB")
        elif op == "handwritten_correction":
            d = ImageDraw.Draw(out)
            # a jagged blue-ish stroke that partially obscures one line of text
            y = random.randint(int(out.size[1] * 0.35), int(out.size[1] * 0.6))
            points = [
                (random.randint(380, 420), y + random.randint(-4, 4))
                for _ in range(8)
            ]
            d.line(points, fill=(20, 30, 150), width=3)
        elif op == "crop_bottom":
            # Remove bottom 30% — simulates phone photo cutting off the footer
            W, H = out.size
            out = out.crop((0, 0, W, int(H * 0.70)))
        # else: ignore unknown op
    return out


# ---------------------------------------------------------------------------
# Seed suite
# ---------------------------------------------------------------------------

def _default_rows_polish() -> List[LabRow]:
    """A realistic adult-female CBC with Polish printed names + decimal commas."""
    return [
        LabRow("Hemoglobina", "HGB", "14,2", 14.2, "g/dL", "12,0 - 16,0"),
        LabRow("Leukocyty", "WBC", "6,8", 6.8, "10^3/µL", "4,5 - 11,0"),
        LabRow("Płytki", "PLT", "230", 230.0, "10^3/µL", "150 - 400"),
        LabRow("MCV", "MCV", "88", 88.0, "fL", "80 - 100"),
        LabRow("Kreatynina", "CREATININE", "0,9", 0.9, "mg/dL", "0,6 - 1,1"),
        LabRow("ALT (GPT)", "ALT", "22", 22.0, "U/L", "7 - 45"),
        LabRow("AST (GOT)", "AST", "19", 19.0, "U/L", "10 - 40"),
        LabRow("Mocznik", "UREA", "15", 15.0, "mg/dL", "7 - 20"),
    ]


def _spec_to_case(
    *,
    name: str,
    spec: LabSheetSpec,
    degradations: List[str],
    quality_tier: str,
    notes: str = "",
) -> Dict:
    """Build the test-case JSON next to the rendered image."""
    ground_truth_values: Dict[str, float] = {}
    ground_truth_units: Dict[str, str] = {}
    ground_truth_ref_ranges: Dict[str, Tuple[float, float]] = {}
    for row in spec.rows:
        ground_truth_values[row.canonical] = row.value_number
        ground_truth_units[row.canonical] = row.unit
        # Parse "12,0 - 16,0" into [12.0, 16.0]
        lo_hi = row.ref_range.replace(",", ".").split("-")
        if len(lo_hi) == 2:
            try:
                ground_truth_ref_ranges[row.canonical] = (
                    float(lo_hi[0].strip()),
                    float(lo_hi[1].strip()),
                )
            except ValueError:
                pass
    return {
        "image": f"{name}.png",
        "lab_chain": spec.lab_chain,
        "layout": spec.layout,
        "quality_tier": quality_tier,
        "degradations": degradations,
        "patient": {"age": spec.patient_age, "sex": spec.patient_sex},
        "ground_truth_values": ground_truth_values,
        "ground_truth_units": ground_truth_units,
        "ground_truth_ref_ranges": {k: list(v) for k, v in ground_truth_ref_ranges.items()},
        "ground_truth_collected_at": spec.collected_at,
        "notes": notes,
    }


@dataclass
class SeedEntry:
    name: str
    spec: LabSheetSpec
    degradations: List[str]
    quality_tier: str
    notes: str = ""


def _seed_cases() -> List[SeedEntry]:
    """Return all seed fixtures (5 mandatory + 4 failure-mode extensions)."""
    cases: List[SeedEntry] = []

    # 1. Polish decimal commas throughout (baseline)
    cases.append(SeedEntry(
        name="seed_01_decimal_comma",
        spec=LabSheetSpec(
            lab_chain="DIAGNOSTYKA",
            patient_age=42,
            patient_sex="f",
            collected_at="2026-02-10",
            rows=_default_rows_polish(),
        ),
        degradations=[],
        quality_tier="clean",
        notes="Polish decimal commas ('14,2') must parse as 14.2, not 142.",
    ))

    # 2. Unit swap on HGB — printed as g/L (×10 the canonical)
    rows_unit_swap = _default_rows_polish()
    rows_unit_swap[0] = LabRow("Hemoglobina", "HGB", "142", 14.2, "g/L", "120 - 160")
    cases.append(SeedEntry(
        name="seed_02_unit_swap_hgb_gL",
        spec=LabSheetSpec(
            lab_chain="ALAB",
            patient_age=52,
            patient_sex="m",
            collected_at="2026-03-01",
            rows=rows_unit_swap,
        ),
        degradations=[],
        quality_tier="clean",
        notes="HGB printed as 142 g/L — normalizer must convert to 14.2 g/dL.",
    ))

    # 3. Slight rotation (3°) on top of Polish-comma baseline
    cases.append(SeedEntry(
        name="seed_03_rotation_3deg",
        spec=LabSheetSpec(
            lab_chain="DIAGNOSTYKA",
            patient_age=33,
            patient_sex="m",
            collected_at="2026-03-05",
            rows=_default_rows_polish(),
        ),
        degradations=["rotate_deg_3"],
        quality_tier="mild_blur",
        notes="Mild skew from handheld camera angle.",
    ))

    # 4. Gaussian blur σ=2 + low-quality JPEG
    cases.append(SeedEntry(
        name="seed_04_blur_sigma2",
        spec=LabSheetSpec(
            lab_chain="ALAB",
            patient_age=60,
            patient_sex="f",
            collected_at="2026-03-08",
            rows=_default_rows_polish(),
        ),
        degradations=["gaussian_blur_sigma_2", "jpeg_q_65"],
        quality_tier="heavy_degraded",
        notes="Blurry phone shot, low JPEG quality.",
    ))

    # 5. Two-column layout (alternative layout family)
    cases.append(SeedEntry(
        name="seed_05_two_column",
        spec=LabSheetSpec(
            lab_chain="SYNEVO",
            patient_age=28,
            patient_sex="f",
            collected_at="2026-03-10",
            rows=_default_rows_polish(),
            layout="two_column",
        ),
        degradations=[],
        quality_tier="clean",
        notes="Two-column layout like some private labs use.",
    ))

    # 6. Glare overlay — bright flash blob obscuring the upper half
    cases.append(SeedEntry(
        name="seed_06_glare",
        spec=LabSheetSpec(
            lab_chain="DIAGNOSTYKA",
            patient_age=45,
            patient_sex="m",
            collected_at="2026-03-15",
            rows=_default_rows_polish(),
        ),
        degradations=["glare", "jpeg_q_75"],
        quality_tier="heavy_degraded",
        notes="Strong flash glare on upper scan. OCR must read through the white blob.",
    ))

    # 7. Handwritten correction — pen scribble over the WBC value
    rows_hw = _default_rows_polish()
    # Slightly different value so the correction stands out clearly
    rows_hw[1] = LabRow("Leukocyty", "WBC", "7,2", 7.2, "10^3/µL", "4,5 - 11,0")
    cases.append(SeedEntry(
        name="seed_07_handwritten_correction",
        spec=LabSheetSpec(
            lab_chain="ALAB",
            patient_age=38,
            patient_sex="f",
            collected_at="2026-03-18",
            rows=rows_hw,
        ),
        degradations=["handwritten_correction"],
        quality_tier="heavy_degraded",
        notes="Pen scribble partially covers the WBC row — model must read through the annotation.",
    ))

    # 8. Cropped bottom — footer with collected_at is cut off
    rows_crop = _default_rows_polish()
    cases.append(SeedEntry(
        name="seed_08_cropped_bottom",
        spec=LabSheetSpec(
            lab_chain="SYNEVO",
            patient_age=55,
            patient_sex="m",
            collected_at="2026-03-20",
            rows=rows_crop,
        ),
        degradations=["crop_bottom"],
        quality_tier="mild_blur",
        notes="Bottom 30% cropped — footer missing. collected_at must be null, not confabulated.",
    ))

    # 9. WBC unit swap — reported as cells/µL (×1000 the canonical K/uL)
    rows_wbc_swap = _default_rows_polish()
    rows_wbc_swap[1] = LabRow("Leukocyty", "WBC", "6800", 6.8, "/µL", "4500 - 11000")
    cases.append(SeedEntry(
        name="seed_09_wbc_unit_swap",
        spec=LabSheetSpec(
            lab_chain="DIAGNOSTYKA",
            patient_age=29,
            patient_sex="f",
            collected_at="2026-03-22",
            rows=rows_wbc_swap,
        ),
        degradations=[],
        quality_tier="clean",
        notes="WBC printed as 6800 /µL (cells per µL) — normalizer must convert to 6.8 K/uL (÷1000).",
    ))

    return cases


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def render_spec(spec: LabSheetSpec) -> Image.Image:
    render = LAYOUTS.get(spec.layout)
    if render is None:
        raise ValueError(f"Unknown layout: {spec.layout}")
    return render(spec)


def emit_case(entry: SeedEntry, out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    img = render_spec(entry.spec)
    if entry.degradations:
        img = augment(img, entry.degradations)
    img_path = out_dir / f"{entry.name}.png"
    img.save(img_path, format="PNG")
    case = _spec_to_case(
        name=entry.name,
        spec=entry.spec,
        degradations=entry.degradations,
        quality_tier=entry.quality_tier,
        notes=entry.notes,
    )
    json_path = out_dir / f"{entry.name}.json"
    json_path.write_text(json.dumps(case, indent=2, ensure_ascii=False))
    return img_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic morfologia fixtures.")
    parser.add_argument("--seed", type=int, default=9,
                        help="Number of seed cases to emit (default 9 = full suite).")
    parser.add_argument("--out", type=Path, default=OUT_DIR,
                        help="Output directory.")
    args = parser.parse_args()

    random.seed(42)
    cases = _seed_cases()[: max(5, args.seed)]
    written: List[Path] = []
    for entry in cases:
        img_path, json_path = emit_case(entry, args.out)
        written.extend([img_path, json_path])
    print(f"Wrote {len(written)} files to {args.out}")
    for p in written:
        print(f"  {p.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
