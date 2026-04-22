#!/usr/bin/env python3
"""
BloodAI data preprocessing pipeline.
Converts Synthea + MIMIC data to tokenized sequences for model training.

Usage:
    python data/prepare_corpus.py --synthea-dir data/synthea/ --output data/corpus.txt
    python data/prepare_corpus.py --mimic-dir data/mimic/ --output data/corpus_mimic.txt
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import argparse
import logging

import pandas as pd
import polars as pl

from data.utils import (
    get_lab_token_v2,
    extract_triggers,
    get_age_group,
    load_lab_norms,
    load_icd_mapping,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

LAB_CODES_SYNTHEA = {
    "4544": "HGB",
    "4545": "HCT",
    "4549": "PLT",
    "3025": "MCV",
    "4353": "WBC",
    "3020": "CREATININE",
    "3016": "ALT",
    "3015": "AST",
    "3024": "UREA",
}

LAB_CODES_MIMIC = {
    "51222": "HGB",
    "51221": "HCT",
    "51265": "PLT",
    "51277": "MCV",
    "51301": "WBC",
    "50912": "CREATININE",
    "50861": "ALT",
    "50878": "AST",
    "51006": "UREA",
}

CLASSES = ["POZ", "GASTRO", "HEMATO", "NEFRO", "SOR", "CARDIO", "PULMO", "HEPATO"]
CLASS_LIMITS = {cls: 40000 for cls in CLASSES}


def preprocess_synthea(
    synthea_dir: Path,
    norms_db: Dict,
    icd_mapping: Dict,
    output_file: Path,
) -> int:
    """
    Process Synthea data: load patients → conditions → observations → tokenize.

    Returns number of sequences generated.
    """
    logger.info(f"Processing Synthea data from {synthea_dir}")

    synthea_dir = Path(synthea_dir)
    batch_dirs = sorted(synthea_dir.glob("batch_*"))
    if not batch_dirs:
        logger.warning(f"No batch_* directories found in {synthea_dir}")
        return 0

    sequences = []
    stats = {cls: 0 for cls in CLASSES}

    for batch_dir in batch_dirs:
        csv_dir = batch_dir / "csv"
        if not csv_dir.exists():
            continue

        try:
            patients_df = pd.read_csv(csv_dir / "patients.csv")
            conditions_df = pd.read_csv(csv_dir / "conditions.csv")
            observations_df = pd.read_csv(csv_dir / "observations.csv")
        except FileNotFoundError as e:
            logger.warning(f"Missing CSV in {csv_dir}: {e}")
            continue

        patient_labs = {}
        patient_conditions = {}
        patient_demos = {}

        for _, row in patients_df.iterrows():
            pid = row["Id"]
            patient_demos[pid] = {
                "birth": int(row["BIRTHDATE"][:4]) if isinstance(row["BIRTHDATE"], str) else 1970,
                "gender": "M" if row["GENDER"] == "M" else "F",
            }

        for _, row in conditions_df.iterrows():
            pid = row["PATIENT"]
            code = str(row["CODE"])
            if pid not in patient_conditions:
                patient_conditions[pid] = []
            patient_conditions[pid].append(code)

        for _, row in observations_df.iterrows():
            pid = row["PATIENT"]
            code = str(row["CODE"])
            value = row["VALUE"]

            if code not in LAB_CODES_SYNTHEA:
                continue

            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue

            if pid not in patient_labs:
                patient_labs[pid] = {}

            if LAB_CODES_SYNTHEA[code] not in patient_labs[pid]:
                patient_labs[pid][LAB_CODES_SYNTHEA[code]] = []

            patient_labs[pid][LAB_CODES_SYNTHEA[code]].append(value)

        for pid, labs in patient_labs.items():
            if pid not in patient_demos or pid not in patient_conditions:
                continue

            age = datetime.now().year - patient_demos[pid]["birth"]
            sex = patient_demos[pid]["gender"]

            tokens = [f"AGE_{age}", f"SEX_{sex}"]

            for test_name, values in labs.items():
                avg_val = sum(values) / len(values)
                token = get_lab_token_v2(test_name, avg_val, age, sex, norms_db)
                tokens.append(token)

            triggers = extract_triggers(tokens)
            for trigger in triggers[:3]:
                tokens.append(f"TRIGGER_{trigger}")

            target_classes = set()
            for icd_code in patient_conditions[pid]:
                for class_name, icd_prefixes in icd_mapping.items():
                    if any(icd_code.startswith(prefix) for prefix in icd_prefixes):
                        target_classes.add(class_name)
                        break

            if not target_classes:
                target_classes.add("POZ")

            target_str = ",".join(sorted(target_classes))
            sequence_str = " ".join(tokens) + f" TARGET_{target_str}"

            sequences.append((sequence_str, target_classes))

            for cls in target_classes:
                if cls in stats:
                    stats[cls] += 1

    logger.info(f"Generated {len(sequences)} sequences from Synthea")
    logger.info(f"Class distribution: {stats}")

    sequences = balance_classes(sequences, target_ratio=0.6)

    with open(output_file, "w") as f:
        for seq, _ in sequences:
            f.write(seq + "\n")

    logger.info(f"Wrote {len(sequences)} sequences to {output_file}")
    return len(sequences)


def balance_classes(
    sequences: List[Tuple[str, Set[str]]],
    target_ratio: float = 0.6,
) -> List[Tuple[str, Set[str]]]:
    """
    Oversample minority classes to achieve target distribution.

    Args:
        sequences: list of (sequence_str, target_classes_set) tuples
        target_ratio: target ratio of most common class
    """
    class_counts = {cls: 0 for cls in CLASSES}
    for _, targets in sequences:
        for cls in targets:
            if cls in class_counts:
                class_counts[cls] += 1

    max_count = max(class_counts.values()) if class_counts else 1
    target_min_count = int(max_count * target_ratio)

    balanced = list(sequences)

    for cls, count in class_counts.items():
        if count < target_min_count:
            to_add = target_min_count - count
            candidates = [seq for seq, targets in sequences if cls in targets]
            if candidates:
                additions = random.choices(candidates, k=to_add)
                balanced.extend([(seq, set(targets)) for seq, targets in additions])

    return balanced


def train_val_split(
    sequences: List[str],
    val_ratio: float = 0.2,
    seed: int = RANDOM_SEED,
) -> Tuple[List[str], List[str]]:
    """
    Simple random split (ideally would be patient-level for real data).

    Args:
        sequences: list of sequence strings
        val_ratio: validation set ratio
        seed: random seed

    Returns:
        (train_sequences, val_sequences)
    """
    random.seed(seed)
    random.shuffle(sequences)

    split_idx = int(len(sequences) * (1 - val_ratio))
    train = sequences[:split_idx]
    val = sequences[split_idx:]

    return train, val


def main():
    parser = argparse.ArgumentParser(description="Prepare BloodAI training corpus")
    parser.add_argument("--synthea-dir", type=Path, help="Path to Synthea data directory")
    parser.add_argument("--mimic-dir", type=Path, help="Path to MIMIC data directory")
    parser.add_argument("--output", type=Path, default=Path("data/corpus.txt"))
    parser.add_argument("--no-balance", action="store_true", help="Skip class balancing")

    args = parser.parse_args()

    config_dir = Path(__file__).parent.parent / "config"
    norms_db = load_lab_norms(config_dir / "lab_norms.json")
    icd_mapping = load_icd_mapping(config_dir / "icd_mapping.json")

    total_sequences = 0

    if args.synthea_dir:
        synthea_seqs = preprocess_synthea(
            args.synthea_dir,
            norms_db,
            icd_mapping,
            args.output,
        )
        total_sequences += synthea_seqs

    logger.info(f"Total sequences: {total_sequences}")
    logger.info(f"Corpus written to {args.output}")


if __name__ == "__main__":
    main()
