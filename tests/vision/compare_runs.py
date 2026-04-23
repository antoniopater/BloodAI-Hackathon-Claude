"""Champion / challenger comparison for two run-log JSONL files.

Typical use:
    # Refresh caches under v1 (champion)
    pytest tests/vision --live --prompt=v1
    # Refresh caches under v2 (challenger)
    pytest tests/vision --live --prompt=v2
    # Compare the latest two run files
    python tests/vision/compare_runs.py v1 v2

The script reads the most recent run JSONL for each prompt version under
`tests/vision/runs/` and prints a side-by-side summary using
`tests.vision.metrics.summarize`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.vision.metrics import summarize

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def _latest_run_for_prompt(version: str) -> Optional[Path]:
    """Return the most recent run file that logged at least one record with
    `prompt_version == version`, or None if none found.
    """
    candidates: List[Path] = sorted(RUNS_DIR.glob("*.jsonl"), reverse=True)
    for path in candidates:
        with path.open() as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("prompt_version") == version:
                    return path
    return None


def _filter_by_prompt(path: Path, version: str) -> Path:
    """Write a temporary JSONL filtered to records of the given prompt version.

    Useful when a single run file contains records from multiple prompts.
    """
    out = path.with_suffix(f".{version}.filtered.jsonl")
    with path.open() as src, out.open("w") as dst:
        for line in src:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("prompt_version") == version:
                dst.write(line)
    return out


def _delta(a: Any, b: Any) -> Any:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return round(b - a, 4)
    return "—"


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def compare(v_champ: str, v_chall: str) -> Dict[str, Any]:
    ch = _latest_run_for_prompt(v_champ)
    cc = _latest_run_for_prompt(v_chall)
    if ch is None:
        print(f"No runs found for champion prompt {v_champ!r}", file=sys.stderr)
        return {}
    if cc is None:
        print(f"No runs found for challenger prompt {v_chall!r}", file=sys.stderr)
        return {}

    champ_filtered = _filter_by_prompt(ch, v_champ)
    chall_filtered = _filter_by_prompt(cc, v_chall)
    champ = summarize(champ_filtered)
    chall = summarize(chall_filtered)

    print(f"\nChampion:   prompt={v_champ}  file={ch.name}")
    print(f"Challenger: prompt={v_chall}  file={cc.name}")
    print()
    headers = ("metric", v_champ, v_chall, "Δ")
    rows = [
        ("calls",             champ.get("calls"),            chall.get("calls")),
        ("exact_match_rate",  champ.get("exact_match_rate"), chall.get("exact_match_rate")),
        ("unit_swap_rate",    champ.get("unit_swap_rate"),   chall.get("unit_swap_rate")),
        ("ece",               champ.get("ece"),              chall.get("ece")),
        ("latency_p95_ms",    champ.get("latency_p95_ms"),   chall.get("latency_p95_ms")),
        ("total_cost_usd",    champ.get("total_cost_usd"),   chall.get("total_cost_usd")),
    ]
    widths = [max(len(str(h)), 18) for h in headers]
    fmt_row = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths))
    print(fmt_row(headers))
    print(fmt_row(["-" * w for w in widths]))
    for name, a, b in rows:
        print(fmt_row([name, _fmt(a), _fmt(b), _fmt(_delta(a, b))]))

    # Per-field F1 delta table
    champ_f1 = (champ.get("per_field_prf1") or {})
    chall_f1 = (chall.get("per_field_prf1") or {})
    params = sorted(set(champ_f1) | set(chall_f1))
    if params:
        print("\nPer-field F1:")
        print(fmt_row(("param", v_champ, v_chall, "Δ")))
        print(fmt_row(["-" * w for w in widths]))
        for p in params:
            a = champ_f1.get(p, {}).get("F1")
            b = chall_f1.get(p, {}).get("F1")
            print(fmt_row([p, _fmt(a), _fmt(b), _fmt(_delta(a, b))]))

    return {"champion": champ, "challenger": chall}


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare two prompt versions' run logs.")
    ap.add_argument("champion", help="Prompt version for the champion, e.g. v1")
    ap.add_argument("challenger", help="Prompt version for the challenger, e.g. v2")
    args = ap.parse_args()
    compare(args.champion, args.challenger)


if __name__ == "__main__":
    main()
