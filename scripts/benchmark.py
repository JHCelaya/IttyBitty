#!/usr/bin/env python
from __future__ import annotations
import argparse, traceback, time, os, sys, re
from pathlib import Path
from typing import Dict, List

# Allow running as "python scripts/benchmark.py ..."
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from scripts.common import sanitize, DEFAULT_MODELS
from app.pdf_io import extract_text_by_page
from app.sections import split_into_sections, stitch_sections

STRUCTURE_PROMPT = (
    "Summarize the following scientific content into a structured abstract with these fields:\n"
    "- Background:\n- Methods:\n- Results:\n- Conclusions:\n"
    "Be concise and strictly use facts from the text.\nTEXT:\n"
)

def load_model(model_id: str, use_fast: bool) -> tuple:
    tok = AutoTokenizer.from_pretrained(model_id, use_fast=use_fast)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    model.eval()
    return tok, model


def _chunk(ids, max_len: int):
    for i in range(0, len(ids), max_len):
        yield ids[i:i+max_len]


def summarize_with(tok, model, text: str, structured=True, max_in_tokens=1024, max_out_tokens=256, num_beams=4) -> str:
    if structured:
        text = STRUCTURE_PROMPT + text
    ids = tok(text, return_tensors="pt", truncation=False).input_ids[0]
    if len(ids) <= max_in_tokens:
        enc = tok(text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
        return tok.decode(out[0], skip_special_tokens=True)
    
    parts: List[str] = []
    for piece in _chunk(ids, max_in_tokens):
        chunk_text = tok.decode(piece, skip_special_tokens=True)
        if structured:
            chunk_text = STRUCTURE_PROMPT + chunk_text
        enc = tok(chunk_text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
        parts.append(tok.decode(out[0], skip_special_tokens=True))

        