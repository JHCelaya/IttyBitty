# app/summarizer.py
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from typing import List
from . import config


_tok = AutoTokenizer.from_pretrained(config.MODEL_ID)
_model = AutoModelForSeq2SeqLM.from_pretrained(config.MODEL_ID)


