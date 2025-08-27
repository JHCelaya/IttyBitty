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