import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


def get_age_group(age: int) -> str:
    """Segment age into clinical groups."""
    if age < 18:
        return "kids"
    elif age < 30:
        return "under_30"
    elif age < 60:
        return "under_60"
    else:
        return "seniors"


def get_lab_token_v2(
    test_name: str,
    value: float,
    age: int,
    sex: str,
    norms_db: Dict,
) -> str:
    """
    Quantize lab value into semantic token based on reference ranges.

    Returns tokens like: HGB_Q1, HGB_Q5, HGB_CRITICAL_LOW, HGB_CRITICAL_HIGH
    If test not in norms_db, returns generic token.
    """
    test_normalized = test_name.upper()

    if test_normalized not in norms_db:
        return f"{test_normalized}_UNKNOWN"

    norms = norms_db[test_normalized]
    age_group = get_age_group(age)
    sex_lower = sex.lower()

    if age_group not in norms or sex_lower not in norms[age_group]:
        return f"{test_normalized}_UNKNOWN"

    range_data = norms[age_group][sex_lower]
    low, high = range_data["low"], range_data["high"]

    if low is None or high is None:
        return f"{test_normalized}_UNKNOWN"

    range_width = high - low
    q_width = range_width / 10

    crit_low = low * 0.6
    crit_high = high * 1.5

    if value < crit_low:
        return f"{test_normalized}_CRITICAL_LOW"
    elif value < low:
        q = int((value - low) / q_width) + 1
        return f"{test_normalized}_Q{min(q, 5)}"
    elif value <= high:
        q = 5 + int((value - low) / q_width)
        return f"{test_normalized}_Q{min(q, 10)}"
    elif value < crit_high:
        q = 6 + int((value - high) / q_width)
        return f"{test_normalized}_Q{min(q, 10)}"
    else:
        return f"{test_normalized}_CRITICAL_HIGH"


def extract_triggers(tokens: List[str]) -> List[str]:
    """
    Extract clinical trigger keywords from token sequence.
    Used to match adaptive interview questions.

    Examples:
        HGB_CRITICAL_LOW -> HGB_LOW
        CREATININE_Q9 -> CREATININE_HIGH
    """
    triggers = []

    for token in tokens:
        if "_CRITICAL_LOW" in token:
            param = token.replace("_CRITICAL_LOW", "")
            triggers.append(f"{param}_LOW")
        elif "_CRITICAL_HIGH" in token:
            param = token.replace("_CRITICAL_HIGH", "")
            triggers.append(f"{param}_HIGH")
        elif "_Q1" in token or "_Q2" in token or "_Q3" in token or "_Q4" in token or "_Q5" in token:
            param = token.split("_Q")[0]
            triggers.append(f"{param}_LOW")
        elif "_Q6" in token or "_Q7" in token or "_Q8" in token or "_Q9" in token or "_Q10" in token:
            param = token.split("_Q")[0]
            triggers.append(f"{param}_HIGH")

    return list(set(triggers))


def load_lab_norms(norms_path: Path) -> Dict:
    """Load reference ranges from JSON config."""
    with open(norms_path) as f:
        return json.load(f)


def load_questions_bank(questions_path: Path) -> Dict[str, List[Dict]]:
    """Load adaptive interview questions from JSON config."""
    with open(questions_path) as f:
        data = json.load(f)

    by_trigger = {}
    for q in data:
        trigger = q.get("trigger", "")
        if trigger not in by_trigger:
            by_trigger[trigger] = []
        by_trigger[trigger].append(q)

    return by_trigger


def load_icd_mapping(mapping_path: Path) -> Dict[str, str]:
    """Load ICD code to specialty mapping."""
    with open(mapping_path) as f:
        return json.load(f)


def tokenize_sequence(tokens: List[str], max_len: int = 128) -> str:
    """Format token sequence as space-separated string, truncated to max_len tokens."""
    seq_str = " ".join(tokens[:max_len])
    return seq_str
