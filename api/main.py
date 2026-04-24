#!/usr/bin/env python3
"""
FastAPI backend for BloodAI triage system.

Endpoints:
- POST /predict — predict triage from lab values
- POST /scan — Opus Vision OCR (see api.scan)
- GET /lab_norms — get reference ranges
- GET /questions/{param} — get adaptive interview questions
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(_static_dir / "index.html")


# Mount the Vision OCR endpoint (POST /scan).
from api.scan import scan_router  # noqa: E402
from api.predict_real import router as predict_real_router  # noqa: E402
from api.explain_mock import router as explain_mock_router  # noqa: E402
from api.nfz import router as nfz_router  # noqa: E402
from api.doctors import router as doctors_router  # noqa: E402
app.include_router(scan_router)
app.include_router(predict_real_router)
app.include_router(explain_mock_router)
app.include_router(nfz_router)
app.include_router(doctors_router)

MODEL_PATH = None
TOKENIZER = None
MODEL = None
LAB_NORMS = None
QUESTIONS_BANK = None
CLASS_THRESHOLDS: Dict[str, float] = {
    "SOR": 0.35, "NEFRO": 0.45, "HEMATO": 0.45, "CARDIO": 0.45,
    "PULMO": 0.45, "GASTRO": 0.45, "HEPATO": 0.45, "POZ": 0.55,
}

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
    """Load model and supporting data on startup."""
    global TOKENIZER, MODEL, LAB_NORMS, QUESTIONS_BANK, MODEL_PATH

    config_dir = Path(__file__).parent.parent / "config"
    data_dir = Path(__file__).parent.parent / "data"
    LAB_NORMS = load_lab_norms(config_dir / "lab_norms.json")
    QUESTIONS_BANK = load_questions_bank(data_dir / "questions.json")

    from api.predict_real import initialize as init_bert
    model_path = Path(__file__).parent.parent / "checkpoints" / "finetune"
    if model_path.exists():
        init_bert(model_path)
    else:
        logger.warning(f"Model not found at {model_path} — /predict will return 503")

    logger.info("BloodAI API ready")


def load_model(model_path: Path):
    """Lazy-load model and calibrated thresholds (if available)."""
    global TOKENIZER, MODEL, CLASS_THRESHOLDS

    logger.info(f"Loading model from {model_path}")
    TOKENIZER = load_tokenizer(model_path / "tokenizer")
    MODEL = BertForMultiLabelClassification.from_pretrained(model_path)
    MODEL = MODEL.to(DEVICE)
    MODEL.eval()

    thresholds_path = model_path / "class_thresholds.json"
    if thresholds_path.exists():
        import json as _json
        with open(thresholds_path) as f:
            CLASS_THRESHOLDS.update(_json.load(f))
        logger.info(f"Loaded calibrated thresholds from {thresholds_path}")
    else:
        logger.info("No class_thresholds.json found — using defaults")

    logger.info("Model loaded")


# Real /predict (BERT inference) — disabled while model is training.
# Swap back in when checkpoints/finetune/ is ready and replace predict_mock_router above.
# @app.post("/predict", response_model=PredictResponse)
# async def predict(request: PredictRequest, model_path: Optional[Path] = None):
#     global TOKENIZER, MODEL
#     if not MODEL:
#         if model_path is None:
#             model_path = Path("checkpoints/finetune/")
#         if not model_path.exists():
#             raise HTTPException(status_code=400, detail=f"Model not found at {model_path}")
#         load_model(model_path)
#     lab_values = {"HGB": request.hgb, "HCT": request.hct, "PLT": request.plt,
#                   "MCV": request.mcv, "WBC": request.wbc, "CREATININE": request.creatinine,
#                   "ALT": request.alt, "AST": request.ast, "UREA": request.urea}
#     tokens = [f"AGE_{request.age}", f"SEX_{request.sex}"]
#     for test_name, value in lab_values.items():
#         if value is not None and value >= 0:
#             token = get_lab_token_v2(test_name, value, request.age, request.sex, LAB_NORMS)
#             tokens.append(token)
#     triggers = extract_triggers(tokens)
#     for trigger in triggers[:3]:
#         tokens.append(f"TRIGGER_{trigger}")
#     sequence_str = " ".join(tokens)
#     encoding = TOKENIZER(sequence_str, max_length=128, padding="max_length",
#                          truncation=True, return_tensors="pt")
#     input_ids = encoding["input_ids"].to(DEVICE)
#     attention_mask = encoding["attention_mask"].to(DEVICE)
#     with torch.no_grad():
#         outputs = MODEL(input_ids=input_ids, attention_mask=attention_mask, output_attentions=True)
#     logits = outputs.logits
#     probs = torch.sigmoid(logits).cpu().numpy()[0]
#     flags = []
#     probabilities = {}
#     for class_idx, class_name in REVERSE_LABEL_MAP.items():
#         prob = float(probs[class_idx])
#         probabilities[class_name] = prob
#         thr = CLASS_THRESHOLDS.get(class_name, 0.5)
#         if prob > thr and class_name != "POZ":
#             flags.append(class_name)
#     if "SOR" in flags:
#         flags = ["SOR"]
#     elif not flags:
#         flags = ["POZ"]
#     attention_data = None
#     if hasattr(outputs, "attentions") and outputs.attentions:
#         last_layer_attention = outputs.attentions[-1][0]
#         cls_attention = last_layer_attention[0].mean(dim=0).cpu().numpy()
#         token_list = TOKENIZER.convert_ids_to_tokens(input_ids[0])
#         attention_data = {token: float(att) for token, att in zip(token_list, cls_attention)
#                           if token not in ["[PAD]", "[CLS]", "[SEP]"]}
#     return PredictResponse(flags=flags, probabilities=probabilities,
#                            attention=attention_data, tokens=tokens)


@app.get("/lab_norms")
async def get_lab_norms():
    """Get reference ranges for all parameters."""
    if not LAB_NORMS:
        config_dir = Path(__file__).parent.parent / "config"
        LAB_NORMS = load_lab_norms(config_dir / "lab_norms.json")

    return LAB_NORMS


@app.get("/questions/{param}")
async def get_questions(param: str, age: Optional[int] = None):
    """Get adaptive interview questions for a parameter trigger.

    QUESTIONS_BANK is keyed by age group (kids/under_30/under_60/seniors).
    We flatten across age groups and filter by trigger, optionally restricting
    to the relevant age group when age is provided.
    """
    global QUESTIONS_BANK
    if not QUESTIONS_BANK:
        data_dir = Path(__file__).parent.parent / "data"
        QUESTIONS_BANK = load_questions_bank(data_dir / "questions.json")

    param_upper = param.upper()
    trigger_low = f"{param_upper}_LOW"
    trigger_high = f"{param_upper}_HIGH"

    from data.utils import get_age_group
    target_group = get_age_group(age) if age is not None else None

    matched = []
    for group, rules in QUESTIONS_BANK.items():
        if target_group and group != target_group:
            continue
        for rule in rules:
            if rule.get("trigger") in (trigger_low, trigger_high):
                matched.append({**rule, "age_group": group})

    return {"questions": matched}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model_loaded": MODEL is not None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
