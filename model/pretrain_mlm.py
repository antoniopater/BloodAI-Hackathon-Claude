#!/usr/bin/env python3
"""
MLM pre-training for BERT on medical corpus.

Usage:
    python model/pretrain_mlm.py --corpus data/corpus.txt --output checkpoints/mlm/
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np

from transformers import (
    BertForMaskedLM,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)

from model.tokenizer import build_tokenizer_from_corpus, get_vocab_size
from model.bert_model import get_bert_config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LineByLineTextDataset(Dataset):
    """Dataset that reads corpus line-by-line and tokenizes on-the-fly.

    TARGET_ labels are stripped so they don't consume vocab slots or get masked.
    """

    def __init__(self, file_path: Path, tokenizer, max_length: int = 128):
        self.tokenizer = tokenizer
        self.max_length = max_length

        logger.info(f"Loading dataset from {file_path}")
        with open(file_path, "r") as f:
            raw = [line.rstrip("\n") for line in f.readlines()]

        # Strip TARGET_ suffix — MLM learns token distributions, not labels
        self.lines = [line.split(" TARGET_")[0] if " TARGET_" in line else line for line in raw]

        logger.info(f"Loaded {len(self.lines)} lines")

    def __len__(self):
        return len(self.lines)

    def __getitem__(self, idx):
        line = self.lines[idx]
        encoding = self.tokenizer(
            line,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
        }


def main():
    parser = argparse.ArgumentParser(description="MLM pre-training for BERT")
    parser.add_argument("--corpus", type=Path, required=True, help="Corpus file path")
    parser.add_argument("--output", type=Path, default=Path("checkpoints/mlm/"))
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--vocab-size", type=int, default=500, help="Vocab size cap (actual size determined by corpus; 300-500 covers all medical tokens)")
    parser.add_argument("--max-samples", type=int, default=None, help="Limit training samples (for quick runs)")

    args = parser.parse_args()

    args.output = Path(args.output)
    args.output.mkdir(parents=True, exist_ok=True)

    logger.info(f"Building tokenizer from {args.corpus}")
    tokenizer = build_tokenizer_from_corpus(
        args.corpus,
        vocab_size=args.vocab_size,
        output_dir=args.output / "tokenizer",
    )
    vocab_size = get_vocab_size(tokenizer)
    logger.info(f"Vocab size: {vocab_size}")

    logger.info("Loading and splitting corpus (90/10 train/val)")
    full_dataset = LineByLineTextDataset(args.corpus, tokenizer)

    import random as _random
    all_lines = list(full_dataset.lines)
    _random.seed(42)
    _random.shuffle(all_lines)
    split_idx = int(len(all_lines) * 0.9)
    train_lines, val_lines = all_lines[:split_idx], all_lines[split_idx:]
    logger.info(f"Split: {len(train_lines)} train / {len(val_lines)} val")

    full_dataset.lines = train_lines
    dataset = full_dataset

    val_dataset = LineByLineTextDataset.__new__(LineByLineTextDataset)
    val_dataset.tokenizer = tokenizer
    val_dataset.max_length = full_dataset.max_length
    val_dataset.lines = val_lines

    if args.max_samples and args.max_samples < len(dataset):
        from torch.utils.data import Subset
        dataset = Subset(dataset, range(args.max_samples))
        logger.info(f"Limiting to {args.max_samples} samples")

    logger.info(f"Creating BERT config (vocab_size={vocab_size})")
    config = get_bert_config(vocab_size=vocab_size)
    model = BertForMaskedLM(config)

    logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M")

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm_probability=0.15,
        mlm=True,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {
            "params": [
                p
                for n, p in model.named_parameters()
                if not any(nd in n for nd in no_decay)
            ],
            "weight_decay": 0.01,
        },
        {
            "params": [
                p
                for n, p in model.named_parameters()
                if any(nd in n for nd in no_decay)
            ],
            "weight_decay": 0.0,
        },
    ]

    training_args = TrainingArguments(
        output_dir=str(args.output),
        overwrite_output_dir=True,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=500,
        save_total_limit=3,
        save_strategy="epoch",
        eval_strategy="epoch",
        logging_steps=100,
        logging_dir=str(args.output / "logs"),
        report_to="none",
        seed=42,
        dataloader_pin_memory=False,
        dataloader_num_workers=0,
        max_grad_norm=1.0,
        load_best_model_at_end=True,
        metric_for_best_model="loss",
        greater_is_better=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=dataset,
        eval_dataset=val_dataset,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    logger.info("Starting MLM pre-training")
    trainer.train()

    logger.info(f"Saving model to {args.output}")
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output / "tokenizer")

    logger.info("MLM pre-training complete!")


if __name__ == "__main__":
    main()
