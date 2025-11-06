#!/usr/bin/env python
from __future__ import annotations
import argparse, traceback, time, os, sys
from pathlib import Path
from typing import Dict, List, Tuple
import re

if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from app.sections import split_into_sections
from scripts.common import DEFAULT_MODELS, load_model, sanitize
from app.pdf_io import extract_text_by_page

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Simpler, more direct prompts
SECTION_PROMPTS = {
    "abstract": "Summarize this abstract in 2-3 factual sentences. Include the main research question and key findings.\n\n",
    "introduction": "What research question or hypothesis does this paper investigate? What background context is provided? (2-3 sentences)\n\n",
    "methods": "Describe the study design, participants/subjects, and main procedures used. (2-4 sentences)\n\n",
    "results": "What were the main findings? Include any specific numbers, measurements, or statistics mentioned. (2-4 sentences)\n\n",
    "discussion": "What do the authors conclude from their findings? What limitations or implications do they mention? (2-3 sentences)\n\n",
    "conclusion": "Summarize the main conclusions of the paper. (1-2 sentences)\n\n",
}

def clean_summary(text: str, min_words: int = 10) -> str:
    """Remove obvious hallucinations and prompt echoes."""
    if not text or len(text.strip()) < 20:
        return "not reported"
    
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        # Skip obvious junk
        if any(x in line.lower() for x in [
            'summarize', 'return:', 'background:', 'methods:', 'results:', 
            'conclusions:', 'text:', 'rules:', 'mail online', 'cnn.com',
            'back to the page', 'newsquiz', 'write a concise', 'describe the',
            'what were the', 'what do the', 'what research'
        ]):
            continue
        if line and len(line.split()) >= 3:  # At least 3 words
            lines.append(line)
    
    result = ' '.join(lines)
    # Must have minimum word count
    if len(result.split()) < min_words:
        return "not reported"
    return result

def summarize_with_model(tok, model, text: str, max_in: int, max_out: int, beams: int) -> str:
    """Single-pass summarization with the model."""
    # Get safe max length for this model
    safe_max = min(max_in, getattr(model.config, "max_position_embeddings", max_in))
    
    # Encode with truncation
    enc = tok(text, return_tensors="pt", truncation=True, max_length=safe_max)
    enc = {k: v.to(DEVICE) for k, v in enc.items()}
    
    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=max_out,
            num_beams=beams,
            do_sample=False,
            length_penalty=1.0,
            early_stopping=True,
            no_repeat_ngram_size=3,
            repetition_penalty=1.2,
        )
    
    result = tok.decode(out[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)
    return result.replace(" <n> ", "\n").replace("<n>", "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", nargs="+", required=True)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--max_in_tokens", type=int, default=1024)
    ap.add_argument("--max_out_tokens", type=int, default=256)
    ap.add_argument("--num_beams", type=int, default=4)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "benchmark.log"

    def log(msg: str):
        print(msg, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"\n{'='*60}")
    log(f"[INFO] Starting benchmark")
    log(f"[INFO] PDFs: {args.pdf}")
    log(f"[INFO] Models: {args.models}")
    log(f"{'='*60}\n")

    # Extract PDFs
    pdf_texts: Dict[Path, Dict[str, str]] = {}
    for p in args.pdf:
        pdf = Path(p)
        if not pdf.exists():
            log(f"[WARN] Missing: {pdf}")
            continue
        
        try:
            log(f"[INFO] Extracting: {pdf.name}")
            raw = extract_text_by_page(str(pdf))
            log(f"[INFO] Total text length: {len(raw)} characters")
            
            # Try to split into sections
            sections = split_into_sections(raw)
            
            # Log what we found
            log(f"[INFO] Sections detected: {list(sections.keys())}")
            for name, text in sections.items():
                log(f"  - {name}: {len(text)} chars")
            
            # Only keep sections with substantial content
            valid_sections = {}
            for name, text in sections.items():
                if len(text) > 300:  # Need at least 300 chars for meaningful content
                    valid_sections[name] = text
                else:
                    log(f"  - Skipping {name} (too short: {len(text)} chars)")
            
            if not valid_sections:
                log(f"[WARN] No valid sections found, skipping PDF")
                continue
            
            pdf_texts[pdf] = valid_sections
            log(f"[OK] Using {len(valid_sections)} sections: {list(valid_sections.keys())}\n")
            
        except Exception as e:
            log(f"[ERROR] {pdf.name}: {e}")
            traceback.print_exc()

    if not pdf_texts:
        log("[FATAL] No PDFs processed")
        return

    # Load models
    models: Dict[str, Tuple] = {}
    for mid in args.models:
        try:
            log(f"[INFO] Loading {mid}")
            t0 = time.time()
            tok, model = load_model(mid, use_fast=False)
            model.to(DEVICE)
            models[mid] = (tok, model)
            log(f"[OK] Loaded {mid} in {time.time()-t0:.1f}s\n")
        except Exception as e:
            log(f"[ERROR] Failed to load {mid}: {e}\n")
            traceback.print_exc()

    if not models:
        log("[FATAL] No models loaded")
        return

    # Build report
    report_lines = [
        "# Scientific Paper Summarization Benchmark",
        f"- Models: {', '.join(models.keys())}",
        f"- Settings: max_in={args.max_in_tokens}, max_out={args.max_out_tokens}, beams={args.num_beams}",
        ""
    ]

    # Process each PDF with each model
    for pdf, sections in pdf_texts.items():
        report_lines.append(f"## {pdf.stem}")
        report_lines.append(f"_Source_: `{pdf.name}`")
        report_lines.append(f"_Sections found_: {', '.join(sections.keys())}\n")

        for mid, (tok, model) in models.items():
            log(f"[RUN] {pdf.stem} × {mid}")
            log(f"{'='*40}")
            t0 = time.time()
            
            parts = []
            section_order = ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]
            
            for section_name in section_order:
                if section_name not in sections:
                    continue
                
                section_text = sections[section_name]
                prompt = SECTION_PROMPTS.get(section_name, SECTION_PROMPTS["abstract"])
                
                log(f"  [{section_name}] Processing {len(section_text)} chars...")
                
                try:
                    summary = summarize_with_model(
                        tok, model,
                        prompt + section_text,
                        args.max_in_tokens,
                        args.max_out_tokens,
                        args.num_beams
                    )
                    summary = clean_summary(summary)
                    
                    if summary != "not reported":
                        parts.append(f"**{section_name.title()}**: {summary}")
                        log(f"  [{section_name}] ✓ Generated {len(summary)} chars")
                    else:
                        log(f"  [{section_name}] ⚠ Summary too short or invalid")
                    
                except Exception as e:
                    log(f"  [{section_name}] ✗ Error: {e}")
                    parts.append(f"**{section_name.title()}**: [Error: {e}]")
            
            if not parts:
                parts.append("**Note**: No valid summaries generated for this model.")
            
            combined = "\n\n".join(parts)
            elapsed = time.time() - t0
            log(f"[OK] Completed in {elapsed:.1f}s")
            log(f"{'='*40}\n")
            
            # Save individual output
            out_file = outdir / f"{sanitize(pdf.stem)}__{sanitize(mid)}.txt"
            out_file.write_text(combined, encoding="utf-8")
            
            # Add to report
            report_lines.append(f"### {mid}")
            report_lines.append("```")
            report_lines.append(combined)
            report_lines.append("```\n")

    # Write report
    report_path = outdir / "benchmark_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    log(f"\n{'='*60}")
    log(f"[SUCCESS] Report saved: {report_path}")
    log(f"[SUCCESS] Individual files in: {outdir.resolve()}")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()