"""
Shared helpers for IttyBitty scripts:
- model loading
- hierarchical summarize
- PDF processing
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import re

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Reuse app utilities
from app.pdf_io import extract_text_by_page
from app.sections import split_into_sections, stitch_sections


DEFAULT_MODELS = [
    "google/pegasus-pubmed",
    "google/pegasus-arxiv",
    "facebook/bart-large-cnn",
    "allenai/led-base-16384",
]


STRUCTURE_PROMPT = (
    "Summarize the following scientific content into a structured abstract with these fields:\n"
    "- Background:\n- Methods:\n- Results:\n- Conclusions:\n"
    "Be concise and strictly use facts from the text.\nTEXT:\n"
)

def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def load_model(model_id: str, use_fast: bool = True):
    """Load tokenizer and model once for a given model_id."""
    tok = AutoTokenizer.from_pretrained(model_id, use_fast=use_fast)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    model.eval()
    return tok, model