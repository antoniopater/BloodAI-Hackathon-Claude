#!/usr/bin/env python3
"""
FastAPI backend for BloodAI triage system.

Endpoints:
- POST /predict — predict triage from lab values
- GET /lab_norms — get reference ranges
- GET /questions/{param} — get adaptive interview questions
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from model.tokenizer import load_tokenizer
from model.bert_model import BertForMultiLabelClassification, LABEL_MAP, REVERSE_LABEL_MAP
from data.utils import (
    get_lab_token_v2,
    extract_triggers,
    load_lab_norms,
    load_questions_bank,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BloodAI Triage API", version="1.0")

MODEL_PATH = None
TOKENIZER = None
MODEL = None
LAB_NORMS = None
QUESTIONS_BANK = None

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class PredictRequest(BaseModel):
    age: int
    sex: str
    hgb: Optional[float] = None
    hct: Optional[float] = None
    plt: Optional[float] = None
    mcv: Optional[float] = None
    wbc: Optional[float] = None
    creatinine: Optional[float] = None
    alt: Optional[float] = None
    ast: Optional[float] = None
    urea: Optional[float] = None


class PredictResponse(BaseModel):
    flags: List[str]
    probabilities: Dict[str, float]
    attention: Optional[Dict[str, float]] = None
    tokens: Optional[List[str]] = None


@app.on_event("startup")
async def startup():
    """Load model on startup (lazy loading)."""
    global TOKENIZER, MODEL, LAB_NORMS, QUESTIONS_BANK, MODEL_PATH

    config_dir = Path(__file__).parent.parent / "config"
    LAB_NORMS = load_lab_norms(config_dir / "lab_norms.json")
    QUESTIONS_BANK = load_questions_bank(config_dir / "questions.json")

    logger.info("BloodAI API ready")


def load_model(model_path: Path):
    """Lazy-load model."""
    global TOKENIZER, MODEL

    logger.info(f"Loading model from {model_path}")

    TOKENIZER = load_tokenizer(model_path / "tokenizer")
    MODEL = BertForMultiLabelClassification.from_pretrained(model_path)
    MODEL = MODEL.to(DEVICE)
    MODEL.eval()

    logger.info("Model loaded")


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest, model_path: Optional[Path] = None):
    """
    Predict triage from lab values.

    Args:
        request: patient demographics and lab values
        model_path: optional override for model checkpoint

    Returns:
        triage flags, probabilities per class, and attention weights
    """
    global TOKENIZER, MODEL

    if not MODEL:
        if model_path is None:
            model_path = Path("checkpoints/finetune/")
        if not model_path.exists():
            raise HTTPException(status_code=400, detail=f"Model not found at {model_path}")
        load_model(model_path)

    lab_values = {
        "HGB": request.hgb,
        "HCT": request.hct,
        "PLT": request.plt,
        "MCV": request.mcv,
        "WBC": request.wbc,
        "CREATININE": request.creatinine,
        "ALT": request.alt,
        "AST": request.ast,
        "UREA": request.urea,
    }

    tokens = [f"AGE_{request.age}", f"SEX_{request.sex}"]

    for test_name, value in lab_values.items():
        if value is not None and value >= 0:
            token = get_lab_token_v2(test_name, value, request.age, request.sex, LAB_NORMS)
            tokens.append(token)

    triggers = extract_triggers(tokens)
    for trigger in triggers[:3]:
        tokens.append(f"TRIGGER_{trigger}")

    sequence_str = " ".join(tokens)

    encoding = TOKENIZER(
        sequence_str,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    input_ids = encoding["input_ids"].to(DEVICE)
    attention_mask = encoding["attention_mask"].to(DEVICE)

    with torch.no_grad():
        outputs = MODEL(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_attentions=True,
        )

    logits = outputs.logits
    probs = torch.sigmoid(logits).cpu().numpy()[0]

    flags = []
    probabilities = {}

    for class_idx, class_name in REVERSE_LABEL_MAP.items():
        prob = float(probs[class_idx])
        probabilities[class_name] = prob

        if class_name == "SOR" and prob > 0.35:
            flags.append("SOR")
        elif class_name != "SOR" and class_name != "POZ" and prob > 0.55:
            flags.append(class_name)

    if not flags:
        flags = ["POZ"]

    attention_data = None
    if hasattr(outputs, "attentions") and outputs.attentions:
        last_layer_attention = outputs.attentions[-1][0]
        cls_attention = last_layer_attention[0].mean(dim=0).cpu().numpy()

        token_list = TOKENIZER.convert_ids_to_tokens(input_ids[0])
        attention_data = {
            token: float(att) for token, att in zip(token_list, cls_attention)
            if token not in ["[PAD]", "[CLS]", "[SEP]"]
        }

    return PredictResponse(
        flags=flags,
        probabilities=probabilities,
        attention=attention_data,
        tokens=tokens,
    )


@app.get("/lab_norms")
async def get_lab_norms():
    """Get reference ranges for all parameters."""
    if not LAB_NORMS:
        config_dir = Path(__file__).parent.parent / "config"
        LAB_NORMS = load_lab_norms(config_dir / "lab_norms.json")

    return LAB_NORMS


@app.get("/questions/{param}")
async def get_questions(param: str):
    """Get adaptive interview questions for a parameter."""
    if not QUESTIONS_BANK:
        config_dir = Path(__file__).parent.parent / "config"
        QUESTIONS_BANK = load_questions_bank(config_dir / "questions.json")

    trigger_key = f"{param.upper()}_LOW"

    if trigger_key not in QUESTIONS_BANK:
        trigger_key = f"{param.upper()}_HIGH"

    if trigger_key not in QUESTIONS_BANK:
        return {"questions": []}

    return {"questions": QUESTIONS_BANK[trigger_key]}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model_loaded": MODEL is not None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
