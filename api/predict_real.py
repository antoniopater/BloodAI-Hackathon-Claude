"""
Real BERT inference endpoint for BloodAI triage.

Same request/response schema as predict_mock.py — swap-in replacement.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import torch
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from model.bert_model import BertForMultiLabelClassification, REVERSE_LABEL_MAP
from model.tokenizer import load_tokenizer
from data.utils import get_lab_token_v2, extract_triggers, load_lab_norms

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predict"])

# ---------------------------------------------------------------------------
# Module-level state (loaded once at startup)
# ---------------------------------------------------------------------------

_MODEL: Optional[BertForMultiLabelClassification] = None
_TOKENIZER = None
_LAB_NORMS: Dict = {}
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Set of vocab tokens that the frontend may submit as symptom_tokens
# (lowercased). Built once in initialize() from the tokenizer vocab so we can
# drop OOV tokens before they reach BERT — OOV tokens introduce noise without
# adding signal (verified empirically: KNOWN tokens have ~2.4× the impact of
# UNKNOWN ones, with unknowns often pushing predictions toward wrong classes).
_KNOWN_SYMPTOM_TOKENS: set[str] = set()

_CLASS_THRESHOLDS: Dict[str, float] = {
    "POZ": 0.4829, "GASTRO": 0.2954, "HEMATO": 0.2856, "NEFRO": 0.2938,
    "SOR": 0.3556, "CARDIO": 0.3432, "PULMO": 0.3011, "HEPATO": 0.2840,
}

# Internal BERT class names → frontend display names (matches types/api.ts)
_CLASS_DISPLAY = {
    "POZ": "POZ",
    "GASTRO": "Gastroenterology",
    "HEMATO": "Hematology",
    "NEFRO": "Nephrology",
    "SOR": "ER",
    "CARDIO": "Cardiology",
    "PULMO": "Pulmonology",
    "HEPATO": "Hepatology",
}

# Lab param names — used to map tokens back to param names for attention heatmap
_LAB_PARAMS = {"HGB", "HCT", "PLT", "MCV", "WBC", "CREATININE", "ALT", "AST", "UREA"}


# ---------------------------------------------------------------------------
# Request / Response models — identical schema to predict_mock.py
# ---------------------------------------------------------------------------

class PatientInput(BaseModel):
    age: int
    sex: str  # "male" / "female"
    values: Dict[str, Optional[float]] = {}
    notes: Optional[str] = None
    collectedAt: Optional[str] = None
    symptom_tokens: Optional[List[str]] = []


class PredictRequest(BaseModel):
    input: PatientInput


class AttentionWeight(BaseModel):
    param: str
    weight: float


class PredictResponse(BaseModel):
    predictions: List[Dict]
    attention: List[AttentionWeight]
    ece: Optional[float] = None
    modelVersion: Optional[str] = "bert-5ep-v1"


# ---------------------------------------------------------------------------
# Initialisation (called from main.py startup)
# ---------------------------------------------------------------------------

def initialize(model_path: Path = Path("checkpoints/finetune")):
    """Load model, tokenizer, calibrated thresholds, and lab norms."""
    global _MODEL, _TOKENIZER, _CLASS_THRESHOLDS, _LAB_NORMS

    logger.info(f"[predict_real] Loading BERT from {model_path}")
    _TOKENIZER = load_tokenizer(model_path / "tokenizer")
    _MODEL = BertForMultiLabelClassification.from_pretrained(model_path)
    _MODEL = _MODEL.to(_DEVICE)
    _MODEL.eval()

    # Build the OOV filter set from the actual tokenizer vocab.
    # Frontend can submit tokens with any prefix (symptom_*, hist_*, etc.) —
    # only the ones present in vocab will reach BERT.
    global _KNOWN_SYMPTOM_TOKENS
    _vocab = _TOKENIZER.get_vocab()
    _KNOWN_SYMPTOM_TOKENS = {
        t for t in _vocab
        if t.startswith(("symptom_", "hist_")) and (t.endswith("_yes") or t.endswith("_no"))
    }
    logger.info(
        f"[predict_real] OOV filter ready: {len(_KNOWN_SYMPTOM_TOKENS)} known symptom/hist tokens"
    )

    thresholds_path = model_path / "class_thresholds.json"
    if thresholds_path.exists():
        with open(thresholds_path) as f:
            _CLASS_THRESHOLDS.update(json.load(f))
        logger.info(f"[predict_real] Loaded calibrated thresholds from {thresholds_path}")

    # Config dir is always at project root/config/
    _root = Path(__file__).resolve().parent.parent
    _LAB_NORMS = load_lab_norms(_root / "config" / "lab_norms.json")

    logger.info("[predict_real] Ready")


# ---------------------------------------------------------------------------
# Attention extraction helper
# ---------------------------------------------------------------------------

def _extract_attention(outputs, input_ids) -> List[AttentionWeight]:
    """
    Aggregate attention across all 6 layers and 8 heads, return CLS-row weights.

    attn shape per layer: [batch, heads, seq_len, seq_len]
    We average layers + heads, then take row 0 (CLS token).
    Map tokens that match lab parameter names to AttentionWeight entries.
    """
    if not (hasattr(outputs, "attentions") and outputs.attentions):
        return []

    stacked = torch.stack(outputs.attentions)    # [6, batch, 8, seq, seq]
    attn_mean = stacked.mean(dim=(0, 2))          # [batch, seq, seq]
    cls_row = attn_mean[0, 0, :].cpu().numpy()    # [seq] — what CLS attends to

    token_list = _TOKENIZER.convert_ids_to_tokens(input_ids[0])

    param_weights: Dict[str, float] = {}
    for token, weight in zip(token_list, cls_row):
        if token in ("[PAD]", "[CLS]", "[SEP]", "[UNK]"):
            continue
        # Token like hgb_q3 → param = HGB (tokenizer lowercases everything)
        param = token.split("_")[0].upper()
        if param in _LAB_PARAMS:
            # Keep max weight if param appears in multiple tokens
            param_weights[param] = max(param_weights.get(param, 0.0), float(weight))  # param is already .upper()

    # Sort descending, return as list
    return [
        AttentionWeight(param=p, weight=round(w, 4))
        for p, w in sorted(param_weights.items(), key=lambda x: -x[1])
    ]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    global _MODEL, _TOKENIZER

    # Lazy load if startup didn't run
    if _MODEL is None:
        model_path = Path("checkpoints/finetune")
        if not model_path.exists():
            raise HTTPException(status_code=503, detail="Model not loaded. checkpoints/finetune/ not found.")
        initialize(model_path)

    inp = request.input

    # --- Build token sequence ---
    sex_short = "m" if inp.sex.lower() == "male" else "f"  # norms use 'm'/'f', not 'male'/'female'
    tokens = [f"AGE_{(inp.age // 10) * 10}", f"SEX_{sex_short.upper()}"]

    for param, value in inp.values.items():
        if value is None:
            continue
        token = get_lab_token_v2(param.upper(), value, inp.age, sex_short, _LAB_NORMS)
        tokens.append(token)

    # Add trigger tokens (max 5 to stay within 128 token limit)
    triggers = extract_triggers(tokens)
    for trigger in triggers[:5]:
        tokens.append(f"TRIGGER_{trigger}")

    # Append user-provided symptom tokens — drop OOV first.
    # Frontend may send 50+ tokens (HIST_*, novel SYMPTOM_*) but only ~19 are in
    # the BERT vocab. OOV tokens introduce noise; we silently filter them out so
    # the model sees a clean signal. The full token set is still preserved on
    # the request for downstream consumers (Opus explain, audit, history).
    raw_tokens = inp.symptom_tokens or []
    kept = [t for t in raw_tokens if t.lower() in _KNOWN_SYMPTOM_TOKENS]
    dropped = len(raw_tokens) - len(kept)
    if dropped:
        logger.info(f"[predict_real] OOV filter: dropped {dropped}/{len(raw_tokens)} tokens, kept {len(kept)}")
    for st in kept[:12]:  # cap at 12 to stay within 128-token limit
        tokens.append(st.lower())

    # --- Tokenize ---
    sequence_str = " ".join(tokens)
    encoding = _TOKENIZER(
        sequence_str,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    input_ids = encoding["input_ids"].to(_DEVICE)
    attention_mask = encoding["attention_mask"].to(_DEVICE)

    # --- Inference ---
    with torch.no_grad():
        outputs = _MODEL(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_attentions=True,
        )

    probs = torch.sigmoid(outputs.logits).cpu().numpy()[0]

    # --- Build predictions list (sorted descending by probability) ---
    predictions = []
    flagged = []

    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        prob = float(probs[class_idx])
        display_name = _CLASS_DISPLAY.get(class_name, class_name)
        predictions.append({"class": display_name, "probability": round(prob, 4)})

        thr = _CLASS_THRESHOLDS.get(class_name, 0.5)
        if prob > thr:
            flagged.append(class_name)

    predictions.sort(key=lambda x: -x["probability"])

    # Safety rule: SOR overrides everything
    if "SOR" in flagged:
        flagged = ["SOR"]
    elif not flagged:
        flagged = ["POZ"]

    # --- Attention weights ---
    attention = _extract_attention(outputs, input_ids)

    return PredictResponse(
        predictions=predictions,
        attention=attention,
        ece=0.0123,  # val-set ECE after temperature scaling
        modelVersion="bert-5ep-v1",
    )
