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

def _chunk_token_ids(ids, max_len: int):
    for i in range(0, len(ids), max_len):
        yield ids[i:i+max_len]

def summarize_text_with(
    tok,
    model,
    text: str,
    structured: bool = True,
    max_in_tokens: int = 1024,
    max_out_tokens: int = 256,
    num_beams: int = 4,
) -> str:
    """Hierarchical summarization if input exceeds max_in_tokens."""
    if structured:
        text = STRUCTURE_PROMPT + text
    
    # Tokenize without truncation to decide chunking
    ids = tok(text, return_tensors="pt", truncation=False).input_ids[0]
    if len(ids) <= max_in_tokens:
        enc = tok(text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
        return tok.decode(out[0], skip_special_tokens=True)
    
    
    # Hierarchical: chunk -> summarize chunks -> summarize the summaries
    chunk_summaries: List[str] = []
    for piece in _chunk_token_ids(ids, max_in_tokens):
        chunk_text = tok.decode(piece, skip_special_tokens=True)
        if structured:
            chunk_text = STRUCTURE_PROMPT + chunk_text
        enc = tok(chunk_text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
        chunk_summaries.append(tok.decode(out[0], skip_special_tokens=True))

    combined = "\n".join(chunk_summaries)
    enc = tok(combined, return_tensors="pt", truncation=True)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
    return tok.decode(out[0], skip_special_tokens=True)


def process_pdf(pdf_path: Path, max_sections: int = 5) -> str:
    """Extract text, split into sections, stitch preferred sections."""
    raw = extract_text_by_page(str(pdf_path))
    sections = split_into_sections(raw)
    stitched = stitch_sections(sections, max_sections=max_sections)
    return stitched or raw