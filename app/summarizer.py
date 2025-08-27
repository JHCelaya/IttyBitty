# app/summarizer.py
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from typing import List
from . import config

_tok = AutoTokenizer.from_pretrained(config.MODEL_ID)
_model = AutoModelForSeq2SeqLM.from_pretrained(config.MODEL_ID)

STRUCTURE_PROMPT = """\
Summarize the following scientific content into a structured abstract with these fields:
- Background:
- Methods:
- Results:
- Conclusions:
Be concise and strictly use facts from the text.
TEXT:
"""

def _generate(text: str, max_new_tokens=config.MAX_OUT_TOKENS) -> str:
    enc = _tok(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        out = _model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            num_beams=config.NUM_BEAMS,
        )
    return _tok.decode(out[0], skip_special_tokens=True)
