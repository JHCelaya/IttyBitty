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

def summarize_text_with(tok, model, text: str, structured=True,
                   max_in_tokens=1024, max_out_tokens=256, num_beams=4) -> str:
    if structured:
        text = STRUCTURE_PROMPT + text

    # Cap by model’s position embedding limit if present (e.g., BART≈1024)
    safe_max = min(
        max_in_tokens,
        getattr(getattr(model, "config", None), "max_position_embeddings", max_in_tokens)
    )
    tok.model_max_length = safe_max
    # Get length WITHOUT truncation so we can decide the path
    ids = tok(text, return_tensors="pt", truncation=False).input_ids[0]

    # --- Short path
    if len(ids) <= safe_max:
        enc = tok(text, return_tensors="pt", truncation=True, max_length=safe_max)
        enc = {k: v.to(next(model.parameters()).device) for k, v in enc.items()}
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=max_out_tokens,
                num_beams=max(num_beams, 5),
                do_sample=False,
                length_penalty=1.1,
                early_stopping=True,
                no_repeat_ngram_size=3,
                repetition_penalty=1.15,
            )
        out_text = tok.decode(out[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)
        out_text = out_text.replace(" <n> ", "\n").replace("<n>", "\n")
        return _dedupe_lines(out_text)

    # --- Hierarchical path
    parts: List[str] = []
    for piece in _chunk(ids, safe_max):
        chunk_text = tok.decode(piece, skip_special_tokens=True)  # no max_length arg here
        if structured:
            chunk_text = STRUCTURE_PROMPT + chunk_text
        enc = tok(chunk_text, return_tensors="pt", truncation=True, max_length=safe_max)
        enc = {k: v.to(next(model.parameters()).device) for k, v in enc.items()}
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=max_out_tokens,
                num_beams=max(num_beams, 5),
                do_sample=False,
                length_penalty=1.1,
                early_stopping=True,
                no_repeat_ngram_size=3,
                repetition_penalty=1.15,
            )
        parts.append(tok.decode(out[0], skip_special_tokens=True))

    combined = "\n".join(parts)
    enc = tok(combined, return_tensors="pt", truncation=True, max_length=safe_max)
    enc = {k: v.to(next(model.parameters()).device) for k, v in enc.items()}
    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=max_out_tokens,
            min_new_tokens=min(120, max_out_tokens - 16),  # floor for length
            num_beams=3,                                   # 3 is fine, faster
            do_sample=False,
            length_penalty=1.1,
            early_stopping=True,
            no_repeat_ngram_size=4,                        # stronger anti-repeat
            repetition_penalty=1.2,                        # esp. for pegasus
        )
    final_text = tok.decode(out[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)
    final_text = final_text.replace(" <n> ", "\n").replace("<n>", "\n")
    return _dedupe_lines(final_text)

def _dedupe_lines(s: str) -> str:
    seen = set(); out = []
    for line in [x.strip() for x in s.splitlines() if x.strip()]:
        k = line.lower()
        if k not in seen:
            seen.add(k); out.append(line)
    return "\n".join(out)

def _chunk(ids, max_len: int):
    for i in range(0, len(ids), max_len):
        yield ids[i:i+max_len]

def process_pdf(pdf_path: Path, max_sections: int = 5) -> str:
    raw = extract_text_by_page(str(pdf_path))
    sections = split_into_sections(raw)
    stitched = stitch_sections(sections, max_sections=max_sections)
    return stitched or raw  # <- string

