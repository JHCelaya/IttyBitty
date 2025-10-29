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


def summarize_with(tok, model, text: str, structured=True, max_in_tokens=1024, max_out_tokens=256, num_beams=4) -> str:
    if structured:
        text = STRUCTURE_PROMPT + text
    ids = tok(text, return_tensors="pt", truncation=False).input_ids[0]
    if len(ids) <= max_in_tokens:
        enc = tok(text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
        return tok.decode(out[0], skip_special_tokens=True)
    
    parts: List[str] = []
    for piece in _chunk(ids, max_in_tokens):
        chunk_text = tok.decode(piece, skip_special_tokens=True)
        if structured:
            chunk_text = STRUCTURE_PROMPT + chunk_text
        enc = tok(chunk_text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_out_tokens, num_beams=num_beams)
        parts.append(tok.decode(out[0], skip_special_tokens=True))

        
def process_pdf(pdf: Path, max_sections=5) -> str:
    raw = extract_text_by_page(str(pdf))
    sections = split_into_sections(raw)
    stitched = stitch_sections(sections, max_sections=max_sections)
    return stitched or raw

def main():
    ap = argparse.ArgumentParser(description="Benchmark HF summarizers on PDFs (robust).")
    ap.add_argument("--pdf", nargs="+", required=True, help="One or more PDF paths.")
    ap.add_argument("--models", nargs="+", default=["google/pegasus-pubmed"], help="Model IDs.")
    ap.add_argument("--outdir", default="out", help="Output directory.")
    ap.add_argument("--structured", action="store_true", help="Use structured abstract prompt.")
    ap.add_argument("--max_in_tokens", type=int, default=1024)
    ap.add_argument("--max_out_tokens", type=int, default=256)
    ap.add_argument("--num_beams", type=int, default=4)
    ap.add_argument("--use_fast_tokenizer", action="store_true", help="Require fast tokenizer (needs protobuf).")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "benchmark.log"

    def log(msg: str):
        print(msg, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"[INFO] Starting benchmark; outputs -> {outdir.resolve()}")
    log(f"[INFO] PDFs: {args.pdf}")
    log(f"[INFO] Models: {args.models}")

    # Load PDFs
    pdf_texts: Dict[Path, str] = {}
    for p in args.pdf:
        pdf = Path(p)
        if not pdf.exists():
            log(f"[WARN] Missing PDF: {pdf}")
            continue
        try:
            log(f"[INFO] Extracting: {pdf}")
            pdf_texts[pdf] = process_pdf(pdf)
            log(f"[OK] Extracted: {pdf}")
        except Exception as e:
            log(f"[ERROR] Failed to extract {pdf}: {e!r}")
            log(traceback.format_exc())
            continue

    if not pdf_texts:
        log("[FATAL] No valid PDFs processed. Aborting.")
        return

    # Load models (continue on errors)
    models = {}
    for mid in args.models:
        try:
            log(f"[INFO] Loading model: {mid}")
            t0 = time.time()
            tok, model = load_model(mid, use_fast=args.use_fast_tokenizer)
            models[mid] = (tok, model)
            log(f"[OK] Loaded {mid} in {time.time()-t0:.1f}s")
        except Exception as e:
            log(f"[ERROR] Failed to load model {mid}: {e!r}")
            log(traceback.format_exc())

    if not models:
        log("[FATAL] No models loaded. Aborting.")
        return

    # Build report
    report_lines = []
    report_lines += [
        "# IttyBitty Benchmark Report",
        f"- Structured: `{args.structured}`",
        f"- max_in_tokens: `{args.max_in_tokens}`, max_out_tokens: `{args.max_out_tokens}`, num_beams: `{args.num_beams}`",
        f"- Models: {', '.join(models.keys())}",
        ""
    ]

    for pdf, text in pdf_texts.items():
        pdf_base = pdf.stem
        report_lines.append(f"## {pdf_base}")
        report_lines.append(f"_File_: `{pdf}`\n")

        for mid, (tok, model) in models.items():
            log(f"[RUN] {pdf_base} × {mid}")
            t0 = time.time()
            try:
                summary = summarize_with(
                    tok, model, text,
                    structured=args.structured,
                    max_in_tokens=args.max_in_tokens,
                    max_out_tokens=args.max_out_tokens,
                    num_beams=args.num_beams,
                )
                # print a preview to console for immediate feedback
                preview = summary[:600].replace("\n", " ")
                log(f"[OK] {pdf_base} × {mid} ({time.time()-t0:.1f}s) :: {preview}...")
            except Exception as e:
                summary = f"[ERROR] {e!r}"
                log(f"[ERROR] {pdf_base} × {mid}: {e!r}")
                log(traceback.format_exc())

            # write per-model text regardless
            out_txt = outdir / f"{sanitize(pdf_base)}__{sanitize(mid)}.txt"
            try:
                out_txt.write_text(summary, encoding="utf-8")
            except Exception as e:
                log(f"[ERROR] Writing {out_txt}: {e!r}")

            # add to report
            report_lines += [f"### Model: `{mid}`",
                             "```text",
                             summary,
                             "```",
                             ""]

    # write combined report
    report_md = outdir / "benchmark_report.md"
    try:
        report_md.write_text("\n".join(report_lines), encoding="utf-8")
        log(f"[OK] Wrote report: {report_md}")
        log(f"[OK] Individual outputs in: {outdir.resolve()}")
    except Exception as e:
        log(f"[ERROR] Writing report: {e!r}")

if __name__ == "__main__":
    main()