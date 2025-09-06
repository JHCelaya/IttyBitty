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