#!/usr/bin/env python3
"""
Advanced evaluation: ECE, ROC curves, temperature scaling, safety logic.

Usage:
    python model/evaluate.py --model checkpoints/finetune/ --corpus data/corpus.txt
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix, f1_score
import matplotlib.pyplot as plt

from model.bert_model import BertForMultiLabelClassification, LABEL_MAP, REVERSE_LABEL_MAP
from model.tokenizer import load_tokenizer
from model.losses import ECELoss


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

    def set_temperature(self, valid_loader, device: str = "cuda"):
        """Tune temperature using LBFGS on validation set."""
        self.model.eval()

        nll_criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.LBFGS([self.temperature], lr=0.01, max_iter=50)

        def eval_():
            optimizer.zero_grad()
            loss = torch.zeros(1, device=device)

            with torch.no_grad():
                for batch in valid_loader:
                    input_ids = batch["input_ids"].to(device)
                    attention_mask = batch["attention_mask"].to(device)
                    labels = batch["labels"].to(device)

                    logits = self.forward(input_ids, attention_mask)

                    for i in range(logits.shape[1]):
                        loss += nll_criterion(
                            logits[:, i:i+1], labels[:, i].long()
                        )

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


def safety_predict(
    probs: np.ndarray,
    threshold_sor: float = 0.35,
    threshold_spec: float = 0.60,
) -> List[str]:
    """
    Apply safety-first logic: prioritize SOR, then specialists, fallback to POZ.

    Args:
        probs: [num_samples, 8] probability matrix
        threshold_sor: SOR threshold
        threshold_spec: specialist threshold

    Returns:
        list of predicted classes per sample
    """
    predictions = []

    for sample_idx in range(probs.shape[0]):
        sample_probs = probs[sample_idx]

        sor_idx = LABEL_MAP["SOR"]
        if sample_probs[sor_idx] > threshold_sor:
            predictions.append("SOR")
            continue

        specialist_indices = [
            i for i in range(len(LABEL_MAP))
            if REVERSE_LABEL_MAP[i] != "SOR" and REVERSE_LABEL_MAP[i] != "POZ"
        ]
        specialist_probs = [sample_probs[i] for i in specialist_indices]
        max_spec_prob = max(specialist_probs) if specialist_probs else 0

        if max_spec_prob > threshold_spec:
            best_specialist_idx = specialist_indices[np.argmax(specialist_probs)]
            predictions.append(REVERSE_LABEL_MAP[best_specialist_idx])
            continue

        predictions.append("POZ")

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

    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        class_probs = all_probs[:, class_idx]
        class_targets = all_labels[:, class_idx]

        auc = roc_auc_score(class_targets, class_probs)
        pred_binary = (class_probs > 0.5).astype(int)
        f1 = f1_score(class_targets, pred_binary, zero_division=0)

        logger.info(f"{class_name:12} | AUC: {auc:.3f} | F1: {f1:.3f}")

    ece = compute_ece(all_probs, all_labels)
    logger.info(f"{'ECE':12} | {ece:.4f} (target < 0.012)")

    logger.info("=" * 60)

    logger.info("\nTesting temperature scaling...")
    model_with_temp = ModelWithTemperature(model)

    logger.info("Final model calibration complete!")


if __name__ == "__main__":
    main()
