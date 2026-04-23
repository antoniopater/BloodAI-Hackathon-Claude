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

from data.utils import (
    get_lab_token_v2,
    extract_triggers,
    get_age_group,
    load_lab_norms,
    load_icd_mapping,
    load_questions_bank,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

LAB_CODES_SYNTHEA = {
    "718-7": "HGB",
    "4544-3": "HCT",
    "777-3": "PLT",
    "787-2": "MCV",
    "6690-2": "WBC",
    "38483-4": "CREATININE",
    "2160-0": "CREATININE",
    "1742-6": "ALT",
    "1920-8": "AST",
    "6299-2": "UREA",
    "3094-0": "UREA",
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

# Data augmentation params (applied only when augment=True, i.e. training corpus)
LAB_DROP_PROB = 0.15   # probability to drop a single lab result (simulate missing data)
LAB_NOISE_FACTOR = 0.05  # ±5% value jitter before quantisation

# Maps question intent to ICD-9/ICD-10 prefixes present in MIMIC diagnoses.
# Used to answer adaptive questions for MIMIC patients (no SNOMED available).
ICD_QUESTION_MAPPING: Dict[str, Tuple] = {
    "DIET_CHECK":         ("26", "E4", "E5", "E6"),
    "BRUISING_CHECK":     ("7827", "R233", "287"),
    "VOMIT_CHECK":        ("7870", "R11"),
    "DYSURIA_CHECK":      ("7881", "R30"),
    "HEMATURIA_CHECK":    ("5997", "R31"),
    "HEAVY_PERIODS":      ("6262", "N920", "N921"),
    "ALCOHOL_CHECK":      ("303", "3050", "F10"),
    "GASTRITIS_CHECK":    ("535", "K29", "R10"),
    "GI_BLEED_CHECK":     ("578", "K920", "K921", "K922"),
    "JAUNDICE_CHECK":     ("7824", "R17"),
    "EDEMA_CHECK":        ("7823", "R60", "4280", "I50"),
    "MEDS_CHECK":         ("Z9222", "V5861"),
    "WEIGHT_LOSS_CHECK":  ("7832", "R634"),
    "CHEST_PAIN_CHECK":   ("7865", "R07"),
    "DYSPNEA_CHECK":      ("7860", "R060"),
    "STOMACH_PAIN_CHECK": ("7890", "R10"),
}

# Keyword mapping for Synthea SNOMED condition descriptions
SNOMED_KEYWORDS = {
    "HEMATO": [
        "anemia", "anaemia", "leukemia", "leukaemia", "lymphoma", "thrombocytopenia",
        "polycythemia", "myeloma", "hemolytic", "haemolytic", "aplastic",
    ],
    "NEFRO": [
        "kidney", "renal", "nephro", "glomerulo", "creatinine", "dialysis",
        "chronic kidney", "acute kidney", "proteinuria", "nephrotic",
    ],
    "CARDIO": [
        "ischemic heart", "ischaemic heart", "coronary", "cardiac", "heart failure",
        "atrial fibrillation", "myocardial", "angina", "hypertension", "hypertensive",
        "heart disease", "arrhythmia", "cardiomyopathy",
    ],
    "PULMO": [
        "asthma", "bronchitis", "bronch", "pulmonary", "pneumonia", "emphysema",
        "copd", "respiratory", "sinusitis", "pharyngitis", "laryngitis",
    ],
    "GASTRO": [
        "gastro", "colitis", "crohn", "irritable bowel", "peptic", "ulcer",
        "hepatitis", "cirrhosis", "liver", "gallstone", "cholecystitis",
        "pancreatitis", "diverticulitis", "hernia", "reflux",
    ],
    "HEPATO": [
        "hepatic", "hepatitis", "cirrhosis", "liver fibrosis", "liver disease",
        "jaundice", "fatty liver",
    ],
    "SOR": [
        "laceration", "fracture", "trauma", "injury", "poisoning", "overdose",
        "sepsis", "shock", "acute myocardial infarction", "stroke",
        "pulmonary embolism", "diabetic ketoacidosis", "acute respiratory",
    ],
}


def classify_snomed_description(description: str) -> Set[str]:
    """Map SNOMED condition description to ALL matching specialties (multi-label)."""
    desc_lower = description.lower()
    matched: Set[str] = set()
    for specialty, keywords in SNOMED_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            matched.add(specialty)
    return matched


def preprocess_synthea(
    synthea_dir: Path,
    norms_db: Dict,
    icd_mapping: Dict,
    questions_db: Optional[Dict] = None,
    augment: bool = True,
) -> List[Tuple[str, str]]:
    """
    Process Synthea data: load patients → conditions → observations → tokenize.

    Returns list of (sequence_str, patient_id) tuples.
    """
    logger.info(f"Processing Synthea data from {synthea_dir}")

    synthea_dir = Path(synthea_dir)

    # Resolve csv dirs: support batch_*/csv/, csv/, or files directly in synthea_dir
    def _find_csv_dirs(base: Path):
        batch_dirs = sorted(base.glob("batch_*"))
        if batch_dirs:
            return [d / "csv" for d in batch_dirs]
        if (base / "csv").exists():
            return [base / "csv"]
        if (base / "patients.csv").exists():
            return [base]
        return []

    csv_dirs = _find_csv_dirs(synthea_dir)
    if not csv_dirs:
        logger.warning(f"No Synthea CSV files found in {synthea_dir}")
        return []

    sequences = []
    stats = {cls: 0 for cls in CLASSES}

    for csv_dir in csv_dirs:
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
            description = str(row.get("DESCRIPTION", ""))
            if pid not in patient_conditions:
                patient_conditions[pid] = []
            patient_conditions[pid].append((code, description))

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

            age_decade = int(age / 10) * 10
            tokens = [f"AGE_{age_decade}", f"SEX_{sex}"]

            lab_tokens = []
            for test_name, values in labs.items():
                if augment and random.random() < LAB_DROP_PROB:
                    continue
                avg_val = sum(values) / len(values)
                if augment:
                    avg_val *= random.uniform(1.0 - LAB_NOISE_FACTOR, 1.0 + LAB_NOISE_FACTOR)
                token = get_lab_token_v2(test_name, avg_val, age, sex, norms_db)
                lab_tokens.append(token)
            tokens.extend(lab_tokens)

            triggers = extract_triggers(lab_tokens)
            for trigger in triggers[:3]:
                tokens.append(f"TRIGGER_{trigger}")

            if questions_db:
                patient_snomed_codes = {str(code) for code, _ in patient_conditions.get(pid, [])}
                age_group = get_age_group(age)
                for rule in questions_db.get(age_group, []):
                    if rule.get("trigger") not in triggers:
                        continue
                    if "gender" in rule and rule["gender"].upper() != sex.upper():
                        continue
                    snomed = str(rule.get("snomed_code", ""))
                    has_condition = snomed in patient_snomed_codes
                    tokens.append(rule["token_yes"] if has_condition else rule["token_no"])

            target_classes = set()
            for code, description in patient_conditions[pid]:
                # Try ICD prefix matching first (for MIMIC-style codes)
                icd_matched = False
                for class_name, icd_prefixes in icd_mapping.items():
                    if any(code.startswith(prefix) for prefix in icd_prefixes):
                        target_classes.add(class_name)
                        icd_matched = True
                # Fall back to SNOMED keyword matching (Synthea) — multi-label
                if not icd_matched and description:
                    target_classes.update(classify_snomed_description(description))

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


def _find_mimic_file(mimic_dir: Path, name: str) -> Optional[Path]:
    """Find a MIMIC file by name, checking dir and hosp/ subdir, with or without .gz."""
    candidates = [
        mimic_dir / name,
        mimic_dir / "hosp" / name,
        mimic_dir / (name + ".gz"),
        mimic_dir / "hosp" / (name + ".gz"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def preprocess_mimic(
    mimic_dir: Path,
    norms_db: Dict,
    icd_mapping: Dict,
    questions_db: Optional[Dict] = None,
    augment: bool = True,
) -> List[Tuple[str, str]]:
    """
    Process MIMIC-III/IV data: patients → diagnoses → labs → tokenize.
    Handles ICD-9 and ICD-10 codes.

    Returns list of (sequence_str, patient_id) tuples.
    """
    logger.info(f"Processing MIMIC data from {mimic_dir}")

    mimic_dir = Path(mimic_dir)

    # Load patients
    patients_file = _find_mimic_file(mimic_dir, "patients.csv")
    if patients_file is None:
        logger.warning(f"patients.csv not found in {mimic_dir} or hosp/")
        return []

    logger.info(f"Loading MIMIC patients from {patients_file}...")
    compression = "gzip" if str(patients_file).endswith(".gz") else None
    patients_df = pd.read_csv(patients_file, compression=compression)
    patients_df["subject_id"] = patients_df["subject_id"].astype(str)
    # anchor_age = age at anchor_year (MIMIC-IV uses obfuscated years like 2180 — use anchor_age directly)
    patient_demos = patients_df.set_index("subject_id")[["anchor_age", "gender"]].to_dict("index")
    logger.info(f"Loaded {len(patient_demos)} MIMIC patients")

    # Load diagnoses (ICD-9 and ICD-10)
    patient_diagnoses: Dict[str, List[str]] = {}
    diagnoses_file = _find_mimic_file(mimic_dir, "diagnoses_icd.csv")
    if diagnoses_file:
        logger.info(f"Loading MIMIC diagnoses from {diagnoses_file}...")
        compression = "gzip" if str(diagnoses_file).endswith(".gz") else None
        diag_df = pd.read_csv(diagnoses_file, compression=compression, usecols=["subject_id", "icd_code"])
        diag_df["subject_id"] = diag_df["subject_id"].astype(str)
        diag_df["icd_code"] = diag_df["icd_code"].astype(str)
        for sid, grp in diag_df.groupby("subject_id"):
            patient_diagnoses[sid] = grp["icd_code"].tolist()
        logger.info(f"Loaded diagnoses for {len(patient_diagnoses)} patients")

    # Load lab events (stream to handle 100M+ rows)
    labevents_file = _find_mimic_file(mimic_dir, "labevents.csv.gz") or _find_mimic_file(mimic_dir, "labevents.csv")
    if labevents_file is None:
        logger.warning(f"labevents.csv[.gz] not found in {mimic_dir} or hosp/")
        return []

    logger.info(f"Streaming MIMIC lab events from {labevents_file} (this may take a while)...")
    patient_labs: Dict[str, Dict[str, List[float]]] = {}
    valid_itemids = set(LAB_CODES_MIMIC.keys())
    chunk_size = 500_000
    chunk_count = 0
    compression = "gzip" if str(labevents_file).endswith(".gz") else None

    for chunk in pd.read_csv(
        labevents_file,
        compression=compression,
        chunksize=chunk_size,
        usecols=["subject_id", "itemid", "valuenum"],
    ):
        chunk_count += 1
        if chunk_count % 5 == 0:
            logger.info(f"  Processed {chunk_count * chunk_size:,} rows...")

        chunk["itemid"] = chunk["itemid"].astype(str)
        chunk = chunk[chunk["itemid"].isin(valid_itemids)]
        chunk = chunk.dropna(subset=["valuenum"])
        chunk["subject_id"] = chunk["subject_id"].astype(str)

        for rec in chunk.itertuples(index=False):
            sid = rec.subject_id
            lab_name = LAB_CODES_MIMIC[rec.itemid]
            if sid not in patient_labs:
                patient_labs[sid] = {}
            if lab_name not in patient_labs[sid]:
                patient_labs[sid][lab_name] = []
            patient_labs[sid][lab_name].append(float(rec.valuenum))

    logger.info(f"Loaded lab events for {len(patient_labs)} patients")

    # Build sequences
    sequences = []
    stats = {cls: 0 for cls in CLASSES}

    for subject_id, labs in patient_labs.items():
        if subject_id not in patient_demos:
            continue

        age = int(patient_demos[subject_id]["anchor_age"])
        if age < 18 or age > 120:
            continue

        sex = "M" if patient_demos[subject_id]["gender"] == "M" else "F"

        age_decade = int(age / 10) * 10
        tokens = [f"AGE_{age_decade}", f"SEX_{sex}"]

        # Add lab tokens (use worst value: min for HGB/HCT/PLT, max for others)
        lab_tokens = []
        for test_name in ["HGB", "HCT", "PLT", "MCV", "WBC", "CREATININE", "UREA", "ALT", "AST"]:
            if test_name not in labs or not labs[test_name]:
                continue
            if augment and random.random() < LAB_DROP_PROB:
                continue
            values = labs[test_name]
            val = min(values) if test_name in ["HGB", "HCT", "PLT"] else max(values)
            if augment:
                val *= random.uniform(1.0 - LAB_NOISE_FACTOR, 1.0 + LAB_NOISE_FACTOR)
            token = get_lab_token_v2(test_name, val, age, sex, norms_db)
            lab_tokens.append(token)
        tokens.extend(lab_tokens)

        # Extract triggers
        triggers = extract_triggers(lab_tokens)
        for trigger in triggers[:3]:
            tokens.append(f"TRIGGER_{trigger}")

        # Adaptive questions: check MIMIC ICD diagnoses via ICD_QUESTION_MAPPING
        if questions_db:
            patient_icd_codes = set(patient_diagnoses.get(subject_id, []))
            age_group = get_age_group(age)
            for rule in questions_db.get(age_group, []):
                if rule.get("trigger") not in triggers:
                    continue
                if "gender" in rule and rule["gender"].upper() != sex.upper():
                    continue
                intent = rule.get("intent", "")
                icd_prefixes = ICD_QUESTION_MAPPING.get(intent, ())
                has_condition = any(
                    code.startswith(prefix)
                    for code in patient_icd_codes
                    for prefix in icd_prefixes
                )
                tokens.append(rule["token_yes"] if has_condition else rule["token_no"])

        # Map diagnoses to classes
        target_classes = set()
        if subject_id in patient_diagnoses:
            for icd_code in patient_diagnoses[subject_id]:
                for class_name, icd_prefixes in icd_mapping.items():
                    if any(icd_code.startswith(prefix) for prefix in icd_prefixes):
                        target_classes.add(class_name)
                        break

        if not target_classes:
            has_trigger = any("TRIGGER_" in t for t in tokens)
            if has_trigger:
                target_classes.add("SOR")  # abnormal labs + no known diagnosis → emergency fallback
            else:
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
            candidates = [(seq, targets) for seq, targets in sequences if cls in targets]
            if candidates:
                additions = random.choices(candidates, k=to_add)
                balanced.extend(additions)

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
    data_dir = Path(__file__).parent
    norms_db = load_lab_norms(config_dir / "lab_norms.json")
    icd_mapping = load_icd_mapping(config_dir / "icd_mapping.json")
    questions_db = load_questions_bank(data_dir / "questions.json")
    logger.info(f"Loaded questions for age groups: {list(questions_db.keys())}")

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
            questions_db=questions_db,
            augment=True,
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
            questions_db=questions_db,
            augment=True,
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
        # 3-way patient-level split: 70% train, 10% val, 20% test
        all_pids = sorted(set(pid for _, pid in mimic_sequences))
        random.seed(RANDOM_SEED)
        random.shuffle(all_pids)
        n_test = int(len(all_pids) * mimic_test_ratio)
        n_val = int(len(all_pids) * 0.1)
        test_pids = set(all_pids[:n_test])
        val_pids = set(all_pids[n_test:n_test + n_val])
        mimic_train = [seq for seq, pid in mimic_sequences if pid not in test_pids and pid not in val_pids]
        mimic_val = [seq for seq, pid in mimic_sequences if pid in val_pids]
        mimic_test = [seq for seq, pid in mimic_sequences if pid in test_pids]
        logger.info(f"MIMIC: {len(mimic_train)} train, {len(mimic_val)} val, {len(mimic_test)} test")
    else:
        mimic_train, mimic_val, mimic_test = [], [], []

    # Combine (synthea_train/val are plain strings; mimic lists may be strings too)
    train_sequences = synthea_train + mimic_train
    val_sequences = synthea_val + mimic_val
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
