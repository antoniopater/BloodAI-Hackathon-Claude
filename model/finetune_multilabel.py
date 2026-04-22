#!/usr/bin/env python3
"""
Multi-label fine-tuning with Cost-Sensitive Focal Loss.

Cost matrix and focal loss definition:
  Loss = mean[ (1 - p_t)^γ * BCE(logit, y) * c_j ]
  where: p_t = σ(logit)*y + (1-σ(logit))*(1-y)
         γ = focal loss exponent (controls hard example mining)
         c_j = class-specific cost weight [POZ:1, GASTRO:5, HEMATO:7, NEFRO:7, SOR:10, ...]

Usage:
    python model/finetune_multilabel.py \
        --pretrained checkpoints/mlm/ \
        --train-corpus data/train.txt \
        --val-corpus data/val.txt \
        --output checkpoints/finetune/ \
        --focal-gamma 2.0
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np

from transformers import (
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
    EvalPrediction,
)
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
import numpy as np

from model.bert_model import (
    BertForMultiLabelClassification,
    LABEL_MAP,
    REVERSE_LABEL_MAP,
    get_bert_config,
)
from model.losses import FocalBCELoss, ECELoss
from model.tokenizer import load_tokenizer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COST_MATRIX = {
    "SOR": 10.0,
    "NEFRO": 7.0,
    "HEMATO": 7.0,
    "CARDIO": 5.0,
    "PULMO": 5.0,
    "GASTRO": 5.0,
    "HEPATO": 4.0,
    "POZ": 1.0,
}


class MultiLabelDataset(Dataset):
    """Dataset for multi-label classification."""

    def __init__(self, file_path: Path, tokenizer, max_length: int = 128):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.examples = []

        logger.info(f"Loading dataset from {file_path}")

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if "TARGET_" not in line:
                    continue

                parts = line.rsplit(" TARGET_", 1)
                if len(parts) != 2:
                    continue

                text = parts[0]
                targets_str = parts[1]

                targets_list = targets_str.split(",")
                labels = torch.zeros(len(LABEL_MAP), dtype=torch.float32)

                for target in targets_list:
                    if target in LABEL_MAP:
                        idx = LABEL_MAP[target]
                        labels[idx] = 1.0

                self.examples.append((text, labels))

        logger.info(f"Loaded {len(self.examples)} examples")

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        text, labels = self.examples[idx]

        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": labels,
        }


class MultiLabelTrainer(Trainer):
    """Custom trainer with cost-sensitive FocalBCELoss."""

    def __init__(self, cost_weights: torch.Tensor, focal_gamma: float, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cost_weights = cost_weights.to(self.model.device)
        self.focal_loss = FocalBCELoss(self.cost_weights, gamma=focal_gamma)
        logger.info(f"Initialized FocalBCELoss with gamma={focal_gamma}, cost_weights={cost_weights.tolist()}")

    def compute_loss(self, model, inputs, return_outputs=False):
        labels = inputs.pop("labels")
        outputs = model(**inputs, output_attentions=True)
        logits = outputs.logits

        loss = self.focal_loss(logits, labels)

        return (loss, outputs) if return_outputs else loss


def compute_metrics(eval_pred: EvalPrediction) -> Dict:
    """Compute ROC AUC, F1, precision, recall per class."""
    predictions = eval_pred.predictions
    label_ids = eval_pred.label_ids

    probs = torch.sigmoid(torch.tensor(predictions)).numpy()

    results = {}

    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        try:
            auc = roc_auc_score(label_ids[:, class_idx], probs[:, class_idx])
            results[f"roc_auc_{class_name}"] = auc
        except Exception:
            results[f"roc_auc_{class_name}"] = 0.0

        pred_binary = (probs[:, class_idx] > 0.5).astype(int)
        true_binary = label_ids[:, class_idx].astype(int)

        try:
            f1 = f1_score(true_binary, pred_binary, zero_division=0)
            results[f"f1_{class_name}"] = f1
        except Exception:
            results[f"f1_{class_name}"] = 0.0

        try:
            precision = precision_score(true_binary, pred_binary, zero_division=0)
            results[f"precision_{class_name}"] = precision
        except Exception:
            results[f"precision_{class_name}"] = 0.0

        try:
            recall = recall_score(true_binary, pred_binary, zero_division=0)
            results[f"recall_{class_name}"] = recall
        except Exception:
            results[f"recall_{class_name}"] = 0.0

    ece_loss = ECELoss(n_bins=15)
    ece = ece_loss(
        torch.tensor(predictions, dtype=torch.float32),
        torch.tensor(label_ids, dtype=torch.float32)
    ).item()
    results["ece"] = ece

    macro_auc = np.mean([v for k, v in results.items() if k.startswith("roc_auc_")])
    results["macro_roc_auc"] = macro_auc

    return results


def main():
    parser = argparse.ArgumentParser(description="Fine-tune BERT for multi-label triage")
    parser.add_argument("--pretrained", type=Path, required=True, help="Pre-trained BERT dir")
    parser.add_argument("--train-corpus", type=Path, required=True, help="Train corpus file (patient-level split)")
    parser.add_argument("--val-corpus", type=Path, required=True, help="Val corpus file (patient-level split)")
    parser.add_argument("--output", type=Path, default=Path("checkpoints/finetune/"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--focal-gamma", type=float, default=2.0, help="Focal loss exponent")

    args = parser.parse_args()
    args.output = Path(args.output)
    args.output.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    logger.info(f"Loading tokenizer from {args.pretrained / 'tokenizer'}")
    tokenizer = load_tokenizer(args.pretrained / "tokenizer")

    logger.info("Loading train and val datasets (patient-level split)")
    train_dataset = MultiLabelDataset(args.train_corpus, tokenizer)
    val_dataset = MultiLabelDataset(args.val_corpus, tokenizer)

    logger.info(f"Train: {len(train_dataset)}, Val: {len(val_dataset)}")

    logger.info(f"Loading model from {args.pretrained}")
    model = BertForMultiLabelClassification.from_pretrained(
        args.pretrained,
        output_attentions=True,
    )

    cost_weights_tensor = torch.tensor(
        [COST_MATRIX[REVERSE_LABEL_MAP[i]] for i in range(len(LABEL_MAP))],
        dtype=torch.float32,
    )

    training_args = TrainingArguments(
        output_dir=str(args.output),
        overwrite_output_dir=True,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=300,
        save_total_limit=2,
        save_strategy="epoch",
        evaluation_strategy="epoch",
        logging_steps=50,
        logging_dir=str(args.output / "logs"),
        report_to="none",
        seed=42,
        load_best_model_at_end=True,
        metric_for_best_model="macro_roc_auc",
        dataloader_pin_memory=True,
        dataloader_num_workers=4 if device == "cuda" else 0,
    )

    trainer = MultiLabelTrainer(
        cost_weights=cost_weights_tensor,
        focal_gamma=args.focal_gamma,
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    logger.info("Starting fine-tuning")
    trainer.train()

    logger.info(f"Saving model to {args.output}")
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output / "tokenizer")

    logger.info("Fine-tuning complete!")


if __name__ == "__main__":
    main()
