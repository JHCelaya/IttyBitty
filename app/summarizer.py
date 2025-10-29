from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from typing import List
from app import config

_tok = AutoTokenizer.from_pretrained(config.MODEL_ID)
_model = AutoModelForSeq2SeqLM.from_pretrained(config.MODEL_ID)

STRUCTURE_PROMPT = """Summarize the scientific content into:
- Background
- Methods
- Results
- Conclusions
Rules: Use ONLY facts present in the text. If a detail is not reported, write 'not reported'. Preserve all numbers, units, and key entities. Avoid repetition.
TEXT:
"""

# tokenizing the input text, generate summary, decode back to text
def _generate(text: str, max_new_tokens=config.MAX_OUT_TOKENS) -> str: 
    enc = _tok(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
       out = _model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            num_beams=max(config.NUM_BEAMS, 5),
            do_sample=False,                 # deterministic
            length_penalty=1.1,              # discourages rambling
            early_stopping=True,
            no_repeat_ngram_size=3,          # key anti-repeat
            repetition_penalty=1.15,         # extra guard
        )
       
    text = _tok.decode(out[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)
    # Pegasus newline token → real newline; collapse triples
    text = text.replace(" <n> ", "\n").replace("<n>", "\n")
    return _dedupe_lines(text)

def summarize_text(text: str) -> str: 
    if config.STRUCTURED: 
        text = STRUCTURE_PROMPT + text 
    return _generate(text)

def _dedupe_lines(s: str) -> str:
    seen = set()
    out = []
    for line in [x.strip() for x in s.splitlines() if x.strip()]:
        if line.lower() not in seen:
            seen.add(line.lower())
            out.append(line)
    return "\n".join(out)
