#!/usr/bin/env python3
"""
BloodAI data preprocessing pipeline.
Converts Synthea + MIMIC data to tokenized sequences for model training.

Usage:
    python data/prepare_corpus.py --synthea-dir data/synthea/ --mimic-dir data/mimic/ \
        --output-train data/train.txt --output-val data/val.txt \
        --output-mimic-test data/mimic_test.txt --mimic-test-ratio 0.2
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
) -> List[Tuple[str, str]]:
    """
    Process Synthea data: load patients → conditions → observations → tokenize.

    Returns list of (sequence_str, patient_id) tuples.
    """
    logger.info(f"Processing Synthea data from {synthea_dir}")

    synthea_dir = Path(synthea_dir)
    batch_dirs = sorted(synthea_dir.glob("batch_*"))

    # If no batch_* dirs, try csv/ directly
    if not batch_dirs:
        csv_dir = synthea_dir / "csv"
        if csv_dir.exists():
            batch_dirs = [synthea_dir]
        else:
            logger.warning(f"No batch_* directories or csv/ found in {synthea_dir}")
            return []

    sequences = []
    stats = {cls: 0 for cls in CLASSES}

    for batch_dir in batch_dirs:
        if batch_dir == synthea_dir:
            csv_dir = batch_dir / "csv"
        else:
            csv_dir = batch_dir / "csv"

        if not csv_dir.exists():
            logger.warning(f"CSV dir not found: {csv_dir}")
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

            tokens = [f"PATIENT_{pid}", f"AGE_{age}", f"SEX_{sex}"]

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

            sequences.append((sequence_str, pid))

            for cls in target_classes:
                if cls in stats:
                    stats[cls] += 1

    logger.info(f"Generated {len(sequences)} sequences from Synthea")
    logger.info(f"Class distribution: {stats}")

    return sequences


def preprocess_mimic(
    mimic_dir: Path,
    norms_db: Dict,
    icd_mapping: Dict,
) -> List[Tuple[str, str]]:
    """
    Process MIMIC-III/IV data: patients → diagnoses → labs → tokenize.
    Handles ICD-9 and ICD-10 codes.

    Returns list of (sequence_str, patient_id) tuples.
    """
    logger.info(f"Processing MIMIC data from {mimic_dir}")

    mimic_dir = Path(mimic_dir)

    # Load patients
    patients_file = mimic_dir / "patients.csv.gz"
    if not patients_file.exists():
        logger.warning(f"patients.csv.gz not found in {mimic_dir}")
        return []

    logger.info("Loading MIMIC patients...")
    patients_df = pd.read_csv(patients_file, compression="gzip")
    patient_demos = {}
    for _, row in patients_df.iterrows():
        subject_id = str(row["subject_id"])
        birth_year = int(row["anchor_year"]) - int(row["anchor_age"])
        patient_demos[subject_id] = {
            "birth": birth_year,
            "gender": "M" if row["gender"] == "M" else "F",
        }
    logger.info(f"Loaded {len(patient_demos)} MIMIC patients")

    # Load diagnoses (ICD-9 and ICD-10)
    diagnoses_file = mimic_dir / "diagnoses_icd.csv.gz"
    patient_diagnoses = {}
    if diagnoses_file.exists():
        logger.info("Loading MIMIC diagnoses...")
        diag_df = pd.read_csv(diagnoses_file, compression="gzip")
        for _, row in diag_df.iterrows():
            subject_id = str(row["subject_id"])
            icd_code = str(row["icd_code"])
            if subject_id not in patient_diagnoses:
                patient_diagnoses[subject_id] = []
            patient_diagnoses[subject_id].append(icd_code)
        logger.info(f"Loaded diagnoses for {len(patient_diagnoses)} patients")

    # Load lab events (stream to handle 158M+ rows)
    labevents_file = mimic_dir / "labevents.csv.gz"
    if not labevents_file.exists():
        logger.warning(f"labevents.csv.gz not found in {mimic_dir}")
        return []

    logger.info("Streaming MIMIC lab events (this may take a while)...")
    patient_labs = {}
    chunk_size = 100000
    chunk_count = 0

    for chunk in pd.read_csv(labevents_file, compression="gzip", chunksize=chunk_size):
        chunk_count += 1
        if chunk_count % 10 == 0:
            logger.info(f"  Processed {chunk_count * chunk_size} rows...")

        for _, row in chunk.iterrows():
            subject_id = str(row["subject_id"])
            itemid = str(row["itemid"])
            value = row["valuenum"]

            if itemid not in LAB_CODES_MIMIC:
                continue

            if pd.isna(value):
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            if subject_id not in patient_labs:
                patient_labs[subject_id] = {}

            lab_name = LAB_CODES_MIMIC[itemid]
            if lab_name not in patient_labs[subject_id]:
                patient_labs[subject_id][lab_name] = []

            patient_labs[subject_id][lab_name].append(value)

    logger.info(f"Loaded lab events for {len(patient_labs)} patients")

    # Build sequences
    sequences = []
    stats = {cls: 0 for cls in CLASSES}

    for subject_id, labs in patient_labs.items():
        if subject_id not in patient_demos:
            continue

        age = 2023 - patient_demos[subject_id]["birth"]
        if age < 18 or age > 120:
            continue

        sex = patient_demos[subject_id]["gender"]

        tokens = [f"PATIENT_{subject_id}", f"AGE_{age}", f"SEX_{sex}"]

        # Add lab tokens (use worst value: min for HGB/HCT/PLT, max for others)
        for test_name in ["HGB", "HCT", "PLT", "MCV", "WBC", "CREATININE", "UREA", "ALT", "AST"]:
            if test_name in labs and len(labs[test_name]) > 0:
                values = labs[test_name]
                if test_name in ["HGB", "HCT", "PLT"]:
                    val = min(values)  # Worst (lowest)
                else:
                    val = max(values)  # Worst (highest)

                token = get_lab_token_v2(test_name, val, age, sex, norms_db)
                tokens.append(token)

        # Extract triggers
        triggers = extract_triggers(tokens)
        for trigger in triggers[:3]:
            tokens.append(f"TRIGGER_{trigger}")

        # Map diagnoses to classes
        target_classes = set()
        if subject_id in patient_diagnoses:
            for icd_code in patient_diagnoses[subject_id]:
                for class_name, icd_prefixes in icd_mapping.items():
                    if any(icd_code.startswith(prefix) for prefix in icd_prefixes):
                        target_classes.add(class_name)
                        break

        # MIMIC patients typically don't map to POZ (all have specialist notes)
        if not target_classes:
            target_classes.add("POZ")

        target_str = ",".join(sorted(target_classes))
        sequence_str = " ".join(tokens) + f" TARGET_{target_str}"

        sequences.append((sequence_str, subject_id))

        for cls in target_classes:
            if cls in stats:
                stats[cls] += 1

    logger.info(f"Generated {len(sequences)} sequences from MIMIC")
    logger.info(f"Class distribution: {stats}")

    return sequences


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


def patient_level_split(
    sequences: List[Tuple[str, str]],
    val_ratio: float = 0.2,
    seed: int = RANDOM_SEED,
) -> Tuple[List[str], List[str]]:
    """
    Patient-level split to avoid data leakage.

    Args:
        sequences: list of (sequence_str, patient_id) tuples
        val_ratio: validation set ratio
        seed: random seed

    Returns:
        (train_sequences, val_sequences)
    """
    random.seed(seed)

    # Extract unique patient IDs
    patient_ids = set(patient_id for _, patient_id in sequences)
    patient_ids = sorted(patient_ids)

    # Shuffle and split patients
    random.shuffle(patient_ids)
    split_idx = int(len(patient_ids) * (1 - val_ratio))
    train_patient_ids = set(patient_ids[:split_idx])

    # Split sequences by patient
    train = [seq for seq, pid in sequences if pid in train_patient_ids]
    val = [seq for seq, pid in sequences if pid not in train_patient_ids]

    logger.info(f"Patient-level split: {len(train_patient_ids)} train patients, {len(patient_ids) - split_idx} val patients")
    logger.info(f"Sequences: {len(train)} train, {len(val)} val")

    return train, val


def main():
    parser = argparse.ArgumentParser(description="Prepare BloodAI training corpus")
    parser.add_argument("--synthea-dir", type=Path, help="Path to Synthea data directory")
    parser.add_argument("--mimic-dir", type=Path, help="Path to MIMIC data directory")
    parser.add_argument("--output-train", type=Path, default=Path("data/train.txt"))
    parser.add_argument("--output-val", type=Path, default=Path("data/val.txt"))
    parser.add_argument("--output-mimic-test", type=Path, default=Path("data/mimic_test.txt"))
    parser.add_argument("--mimic-test-ratio", type=float, default=0.2, help="MIMIC hold-out test ratio")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation ratio from Synthea")
    parser.add_argument("--no-balance", action="store_true", help="Skip class balancing")

    args = parser.parse_args()

    config_dir = Path(__file__).parent.parent / "config"
    norms_db = load_lab_norms(config_dir / "lab_norms.json")
    icd_mapping = load_icd_mapping(config_dir / "icd_mapping.json")

    synthea_sequences = []
    mimic_sequences = []

    # Process Synthea
    if args.synthea_dir:
        logger.info("="*60)
        logger.info("SYNTHEA PREPROCESSING")
        logger.info("="*60)
        synthea_seqs_with_pid = preprocess_synthea(
            args.synthea_dir,
            norms_db,
            icd_mapping,
        )
        synthea_sequences = synthea_seqs_with_pid
        logger.info(f"Synthea: {len(synthea_sequences)} sequences")

    # Process MIMIC
    if args.mimic_dir:
        logger.info("="*60)
        logger.info("MIMIC PREPROCESSING")
        logger.info("="*60)
        mimic_seqs = preprocess_mimic(
            args.mimic_dir,
            norms_db,
            icd_mapping,
        )
        mimic_sequences = mimic_seqs
        logger.info(f"MIMIC: {len(mimic_sequences)} sequences")

    # 3-way split: Synthea (train/val), MIMIC (train/val/test)
    synthea_train, synthea_val = patient_level_split(
        synthea_sequences,
        val_ratio=args.val_ratio,
        seed=RANDOM_SEED,
    )
    logger.info(f"Synthea split: {len(synthea_train)} train, {len(synthea_val)} val")

    # MIMIC: 70% train, 10% val, 20% test
    mimic_test_ratio = args.mimic_test_ratio  # 0.2

    if len(mimic_sequences) > 0:
        # First split: test vs rest
        mimic_rest, mimic_test = patient_level_split(
            mimic_sequences,
            val_ratio=mimic_test_ratio,
            seed=RANDOM_SEED,
        )
        logger.info(f"MIMIC: {len(mimic_rest)} rest, {len(mimic_test)} test")

        # Second split: train vs val from rest
        val_ratio_of_rest = 0.1 / (1.0 - mimic_test_ratio)  # ~0.125
        mimic_train, mimic_val = patient_level_split(
            mimic_rest,
            val_ratio=val_ratio_of_rest,
            seed=RANDOM_SEED,
        )
        logger.info(f"MIMIC: {len(mimic_train)} train, {len(mimic_val)} val, {len(mimic_test)} test")
    else:
        mimic_train, mimic_val, mimic_test = [], [], []

    # Combine
    train_sequences = [seq for seq, _ in synthea_train] + mimic_train
    val_sequences = [seq for seq, _ in synthea_val] + mimic_val
    test_sequences = mimic_test

    # Apply balancing if requested
    if not args.no_balance and len(train_sequences) > 0:
        train_with_targets = []
        for seq in train_sequences:
            if "TARGET_" in seq:
                parts = seq.split("TARGET_")
                targets_str = parts[-1]
                targets = set(targets_str.split(","))
                train_with_targets.append((seq, targets))

        if train_with_targets:
            train_sequences = [seq for seq, _ in balance_classes(train_with_targets)]

    # Write outputs
    args.output_train.parent.mkdir(parents=True, exist_ok=True)
    args.output_val.parent.mkdir(parents=True, exist_ok=True)
    args.output_mimic_test.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output_train, "w") as f:
        for seq in train_sequences:
            f.write(seq + "\n")
    logger.info(f"Wrote {len(train_sequences)} sequences to {args.output_train}")

    with open(args.output_val, "w") as f:
        for seq in val_sequences:
            f.write(seq + "\n")
    logger.info(f"Wrote {len(val_sequences)} sequences to {args.output_val}")

    with open(args.output_mimic_test, "w") as f:
        for seq in test_sequences:
            f.write(seq + "\n")
    logger.info(f"Wrote {len(test_sequences)} sequences to {args.output_mimic_test}")

    logger.info("="*60)
    logger.info(f"Total: {len(train_sequences)} train + {len(val_sequences)} val + {len(test_sequences)} test")
    logger.info("="*60)


if __name__ == "__main__":
    main()
