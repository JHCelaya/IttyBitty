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
