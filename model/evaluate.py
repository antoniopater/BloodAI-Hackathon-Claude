#!/usr/bin/env python3
"""
Advanced evaluation: ECE, ROC curves, temperature scaling, safety logic.

Usage:
    python model/evaluate.py --model checkpoints/finetune/ --corpus data/corpus.txt
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix, f1_score
import matplotlib.pyplot as plt

from model.bert_model import BertForMultiLabelClassification, LABEL_MAP, REVERSE_LABEL_MAP
from model.tokenizer import load_tokenizer
from model.losses import ECELoss


class _EvalDataset(Dataset):
    """Minimal dataset for temperature scaling DataLoader."""
    def __init__(self, inputs, labels, tokenizer):
        self.inputs = inputs
        self.labels = labels
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.inputs[idx], max_length=128, padding="max_length",
            truncation=True, return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(),
            "attention_mask": enc["attention_mask"].squeeze(),
            "labels": torch.tensor(self.labels[idx], dtype=torch.float32),
        }


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CRITICAL_KEYWORDS = {
    "CRITICAL_LOW",
    "CRITICAL_HIGH",
    "HGB_CRITICAL",
    "PLT_CRITICAL",
    "CREATININE_CRITICAL",
}


class ModelWithTemperature(nn.Module):
    """Model wrapper with temperature scaling for calibration."""

    def __init__(self, model: BertForMultiLabelClassification):
        super().__init__()
        self.model = model
        self.temperature = nn.Parameter(torch.ones(1) * 1.0)

    def forward(self, input_ids, attention_mask):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits / self.temperature
        return logits

    def set_temperature(self, valid_loader, device: str = "cpu"):
        """Tune temperature using LBFGS on validation set (multi-label BCE)."""
        self.model.eval()
        self.to(device)

        # Collect all logits and labels in one pass (no grad needed here)
        all_logits, all_labels = [], []
        with torch.no_grad():
            for batch in valid_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                all_logits.append(outputs.logits.detach())
                all_labels.append(labels.detach())

        all_logits = torch.cat(all_logits)
        all_labels = torch.cat(all_labels)

        bce = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.LBFGS([self.temperature], lr=0.01, max_iter=50)

        def eval_():
            optimizer.zero_grad()
            loss = bce(all_logits / self.temperature, all_labels)
            loss.backward()
            return loss

        optimizer.step(eval_)
        return self.temperature.item()


def compute_ece(probs: np.ndarray, targets: np.ndarray, n_bins: int = 15) -> float:
    """Compute Expected Calibration Error."""
    ece = 0.0
    count = 0

    for class_idx in range(probs.shape[1]):
        class_probs = probs[:, class_idx]
        class_targets = targets[:, class_idx]

        bin_boundaries = np.linspace(0, 1, n_bins + 1)

        for bin_start, bin_end in zip(bin_boundaries[:-1], bin_boundaries[1:]):
            mask = (class_probs >= bin_start) & (class_probs < bin_end)

            if mask.sum() == 0:
                continue

            avg_confidence = class_probs[mask].mean()
            accuracy = class_targets[mask].astype(float).mean()

            ece += np.abs(avg_confidence - accuracy) * (mask.mean())
            count += 1

    return ece / max(count, 1)


CLASS_THRESHOLDS = {
    "SOR":    0.35,
    "NEFRO":  0.45,
    "HEMATO": 0.45,
    "CARDIO": 0.45,
    "PULMO":  0.45,
    "GASTRO": 0.45,
    "HEPATO": 0.45,
    "POZ":    0.55,
}

# Cost weights per class — same as COST_MATRIX in finetune_multilabel.py
_COST_WEIGHTS = {
    "SOR": 10.0, "NEFRO": 7.0, "HEMATO": 7.0, "CARDIO": 5.0,
    "PULMO": 5.0, "GASTRO": 5.0, "HEPATO": 4.0, "POZ": 1.0,
}


def calibrate_thresholds(
    probs: np.ndarray,
    labels: np.ndarray,
    cost_weights: Dict[str, float] = None,
    output_path: Path = None,
) -> Dict[str, float]:
    """
    Find optimal decision threshold per class by minimising cost-weighted error
    on the ROC curve:  cost(t) = w_c * FNR(t) + FPR(t)

    Args:
        probs:        [N, num_classes] probability matrix (post-sigmoid)
        labels:       [N, num_classes] binary ground-truth
        cost_weights: per-class miss-cost; higher → lower threshold for that class
        output_path:  if given, save thresholds to JSON at this path

    Returns:
        Dict mapping class name → optimal threshold
    """
    if cost_weights is None:
        cost_weights = _COST_WEIGHTS

    thresholds: Dict[str, float] = {}

    logger.info("=" * 60)
    logger.info("THRESHOLD CALIBRATION  (minimise  w·FNR + FPR)")
    logger.info("=" * 60)

    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        class_probs = probs[:, class_idx]
        class_labels = labels[:, class_idx]
        w = cost_weights.get(class_name, 1.0)

        # Need at least one positive to compute ROC
        if class_labels.sum() == 0:
            thresholds[class_name] = CLASS_THRESHOLDS.get(class_name, 0.5)
            logger.warning(f"{class_name:12} | no positives in data — keeping default {thresholds[class_name]:.2f}")
            continue

        fpr_arr, tpr_arr, thr_arr = roc_curve(class_labels, class_probs)
        fnr_arr = 1.0 - tpr_arr
        # Minimise w·FNR + FPR (first point has thr=inf, skip it)
        cost_arr = w * fnr_arr[1:] + fpr_arr[1:]
        best_idx = int(np.argmin(cost_arr))
        best_thr = float(np.clip(thr_arr[1:][best_idx], 0.01, 0.99))

        thresholds[class_name] = round(best_thr, 4)
        logger.info(
            f"{class_name:12} | w={w:4.1f} | "
            f"thr={best_thr:.3f}  "
            f"FNR={fnr_arr[1:][best_idx]:.3f}  FPR={fpr_arr[1:][best_idx]:.3f}"
        )

    logger.info("=" * 60)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(thresholds, f, indent=2)
        logger.info(f"Thresholds saved → {output_path}")

    return thresholds


def safety_predict(
    probs: np.ndarray,
    thresholds: Dict = None,
) -> List[List[str]]:
    """
    Apply safety-first multi-label logic with per-class thresholds.

    Args:
        probs: [num_samples, 8] probability matrix
        thresholds: per-class thresholds (defaults to CLASS_THRESHOLDS)

    Returns:
        list of predicted class lists per sample (multi-label)
    """
    if thresholds is None:
        thresholds = CLASS_THRESHOLDS

    predictions = []

    for sample_idx in range(probs.shape[0]):
        sample_probs = probs[sample_idx]
        classes = []

        for class_idx, class_name in REVERSE_LABEL_MAP.items():
            thr = thresholds.get(class_name, 0.5)
            if sample_probs[class_idx] > thr:
                classes.append(class_name)

        # SOR takes precedence: if flagged, drop other non-SOR classes
        if "SOR" in classes and len(classes) > 1:
            classes = ["SOR"]

        if not classes:
            classes = ["POZ"]

        predictions.append(classes)

    return predictions


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained model")
    parser.add_argument("--model", type=Path, required=True, help="Model checkpoint")
    parser.add_argument("--corpus", type=Path, required=True, help="Evaluation corpus")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")

    args = parser.parse_args()

    device = torch.device(args.device)
    logger.info(f"Using device: {device}")

    logger.info(f"Loading tokenizer from {args.model / 'tokenizer'}")
    tokenizer = load_tokenizer(args.model / "tokenizer")

    logger.info(f"Loading model from {args.model}")
    model = BertForMultiLabelClassification.from_pretrained(args.model)
    model = model.to(device)
    model.eval()

    logger.info("Loading evaluation data")
    all_inputs = []
    all_labels = []

    with open(args.corpus, "r") as f:
        for line in f:
            line = line.strip()
            if "TARGET_" not in line:
                continue

            parts = line.rsplit(" TARGET_", 1)
            if len(parts) != 2:
                continue

            text = parts[0]
            targets_str = parts[1]
            targets_list = targets_str.split(",")

            labels = np.zeros(len(LABEL_MAP))
            for target in targets_list:
                if target in LABEL_MAP:
                    labels[LABEL_MAP[target]] = 1.0

            all_inputs.append(text)
            all_labels.append(labels)

    all_labels = np.array(all_labels)
    logger.info(f"Loaded {len(all_inputs)} examples")

    logger.info("Generating predictions")
    all_probs = []

    with torch.no_grad():
        for i, text in enumerate(all_inputs):
            if (i + 1) % 1000 == 0:
                logger.info(f"Processed {i + 1}/{len(all_inputs)}")

            encoding = tokenizer(
                text,
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )

            input_ids = encoding["input_ids"].to(device)
            attention_mask = encoding["attention_mask"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            probs = torch.sigmoid(logits).cpu().numpy()

            all_probs.append(probs[0])

    all_probs = np.array(all_probs)

    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)

    # --- Pre-calibration metrics (default 0.5 threshold) ---
    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        class_probs = all_probs[:, class_idx]
        class_targets = all_labels[:, class_idx]

        auc = roc_auc_score(class_targets, class_probs)
        pred_binary = (class_probs > 0.5).astype(int)
        f1 = f1_score(class_targets, pred_binary, zero_division=0)

        logger.info(f"{class_name:12} | AUC: {auc:.3f} | F1@0.5: {f1:.3f}")

    ece = compute_ece(all_probs, all_labels)
    logger.info(f"{'ECE':12} | {ece:.4f} (target < 0.012)")
    logger.info("=" * 60)

    # --- Temperature scaling ---
    logger.info("\nCalibrating with temperature scaling...")
    eval_ds = _EvalDataset(all_inputs, all_labels, tokenizer)
    eval_loader = DataLoader(eval_ds, batch_size=64, shuffle=False)
    model_with_temp = ModelWithTemperature(model)
    temp = model_with_temp.set_temperature(eval_loader, device=str(device))
    logger.info(f"Optimal temperature: {temp:.4f}  (1.0 = already calibrated)")

    cal_probs = []
    with torch.no_grad():
        for batch in eval_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            logits = model_with_temp(input_ids, attention_mask)
            cal_probs.append(torch.sigmoid(logits).cpu().numpy())
    cal_probs = np.vstack(cal_probs)
    ece_cal = compute_ece(cal_probs, all_labels)
    logger.info(f"ECE after calibration: {ece_cal:.4f} (before: {ece:.4f})")

    # --- Threshold calibration on ROC curve (post temperature scaling) ---
    thresholds_path = args.model / "class_thresholds.json"
    calibrated_thresholds = calibrate_thresholds(
        cal_probs, all_labels, output_path=thresholds_path
    )

    # --- Final metrics with calibrated thresholds ---
    logger.info("=" * 60)
    logger.info("FINAL METRICS (calibrated thresholds)")
    logger.info("=" * 60)
    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        class_probs = cal_probs[:, class_idx]
        class_targets = all_labels[:, class_idx]
        thr = calibrated_thresholds[class_name]

        auc = roc_auc_score(class_targets, class_probs)
        pred_binary = (class_probs > thr).astype(int)
        f1 = f1_score(class_targets, pred_binary, zero_division=0)
        logger.info(f"{class_name:12} | AUC: {auc:.3f} | F1@{thr:.2f}: {f1:.3f}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
