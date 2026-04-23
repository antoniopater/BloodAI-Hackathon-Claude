from pathlib import Path
from typing import Optional, List
from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, trainers, processors
from transformers import PreTrainedTokenizerFast


def build_tokenizer_from_corpus(
    corpus_path: Path,
    vocab_size: int = 500,
    min_frequency: int = 1,
    output_dir: Optional[Path] = None,
) -> PreTrainedTokenizerFast:
    """
    Build word-level tokenizer from corpus file (one sequence per line).

    Args:
        corpus_path: path to text file with sequences
        vocab_size: target vocab size
        min_frequency: minimum token frequency
        output_dir: where to save tokenizer (optional)

    Returns:
        HuggingFace PreTrainedTokenizerFast
    """

    tokenizer = Tokenizer(models.WordLevel(unk_token="[UNK]"))
    tokenizer.normalizer = normalizers.Lowercase()
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()

    special_tokens = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]

    trainer = trainers.WordLevelTrainer(
        vocab_size=vocab_size,
        min_frequency=min_frequency,
        special_tokens=special_tokens,
    )

    tokenizer.train([str(corpus_path)], trainer)

    tokenizer.post_processor = processors.TemplateProcessing(
        single="[CLS] $A [SEP]",
        pair="[CLS] $A [SEP] $B:1 [SEP]:1",
        special_tokens=[
            ("[CLS]", tokenizer.token_to_id("[CLS]")),
            ("[SEP]", tokenizer.token_to_id("[SEP]")),
        ],
    )

    hf_tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer,
        pad_token="[PAD]",
        unk_token="[UNK]",
        cls_token="[CLS]",
        sep_token="[SEP]",
        mask_token="[MASK]",
    )

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        hf_tokenizer.save_pretrained(output_dir)
        print(f"Tokenizer saved to {output_dir}")

    return hf_tokenizer


def load_tokenizer(tokenizer_dir: Path) -> PreTrainedTokenizerFast:
    """Load pre-trained tokenizer from directory."""
    return PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))


def get_vocab_size(tokenizer: PreTrainedTokenizerFast) -> int:
    """Get vocabulary size of tokenizer."""
    return len(tokenizer.get_vocab())
