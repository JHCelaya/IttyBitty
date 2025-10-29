#!/usr/bin/env python
from __future__ import annotations
import argparse, traceback, time, os, sys
from pathlib import Path
from typing import Dict, List, Tuple

# Allow running as "python -m scripts.benchmark ..."
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from app.sections import split_into_sections, stitch_sections  # used for sectioning
from scripts.common import (
    DEFAULT_MODELS,
    load_model,
    process_pdf,
    sanitize,
    summarize_text_with,
)

import re
from typing import Iterable

_JUNK_PAT = re.compile(r"(Mail Online|CNN|http[s]?://|Return to|Back to the page|Summarize the )", re.I)

def _sentences(s: str) -> Iterable[str]:
    # Lightweight splitter; avoids extra deps
    for chunk in re.split(r"(?<=[.!?])\s+", s.strip()):
        c = chunk.strip()
        if c:
            yield c

def _token_set(s: str) -> set:
    return set(t.lower() for t in re.findall(r"[A-Za-z0-9]+", s))

# Hard blocks for obvious junk / prompt echoes
_JUNK_PAT = re.compile(
    r"(Mail Online|CNN|http[s]?://|Return to|Back to the page|Use the weekly Newsquiz|"
    r"^Summarize\b|^Rules:|^Return:|^Background:|^Methods:|^Results:|^Conclusions:)",
    re.I,
)

def _sentences(s: str) -> Iterable[str]:
    for chunk in re.split(r"(?<=[.!?])\s+", s.strip()):
        c = chunk.strip()
        if c:
            yield c

_WORD = re.compile(r"[A-Za-z0-9]+")

_JUNK_PAT = re.compile(
    r"(Mail Online|CNN|http[s]?://|Return to|Back to the page|Use the weekly Newsquiz|"
    r"^Summarize\b|^Rules:|^Return:)", re.I,
)
_WORD = re.compile(r"[A-Za-z0-9]+")

def _token_set(s: str) -> set:
    return set(t.lower() for t in _WORD.findall(s or ""))

def clean_and_verify(candidate: str,
                     source_text: str,
                     *,
                     min_overlap: float = 0.18,
                     require_digit: bool = False,
                     enforce_overlap: bool = False) -> str:
    """
    - If enforce_overlap=False: only strip obvious junk; keep sentences.
    - If enforce_overlap=True: require modest token overlap with source (default 0.18).
    - If require_digit=True: require at least one digit in the sentence.
    """
    if not candidate or not candidate.strip():
        return "not reported"

    src_tokens = _token_set(source_text)
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", candidate.strip()):
        s = sent.strip()
        if not s:
            continue
        if _JUNK_PAT.search(s):
            continue
        if require_digit and not re.search(r"\d", s):
            continue
        if enforce_overlap:
            toks = _token_set(s)
            if not toks:
                continue
            inter = len(toks & src_tokens)
            union = len(toks | src_tokens) or 1
            if (inter / union) < min_overlap:
                continue
        out.append(s)

    return " ".join(out) if out else "not reported"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

STRUCTURE_PROMPT = (
    "Summarize the following scientific content into a structured abstract with these fields:\n"
    "- Background:\n- Methods:\n- Results:\n- Conclusions:\n"
    "Use ONLY facts stated in the text. Preserve numbers/units. Avoid repetition.\n\nTEXT:\n"
)

# Gentle, factual prompts per section
SECTION_PROMPTS = {
    "abstract": (
        "Write a concise, factual summary of the abstract.\n"
        "Rules: Use ONLY facts in the text. If a detail is missing, write 'not reported'. "
        "Preserve numbers/units. Avoid repetition.\n\n"
    ),
    "introduction": (
        "Summarize the introduction: topic and hypotheses/objectives.\n"
        "Rules: facts only; if missing, write 'not reported'.\n\n"
    ),
    "methods": (
        "Summarize the methods: participants/subjects, design, measures, analyses.\n"
        "Rules: facts only; preserve numbers/units. Use 'not reported' when absent.\n\n"
    ),
    "results": (
        "Summarize the key results.\n"
        "Rules: include numbers/units/stats if present; otherwise 'not reported'. No speculation.\n\n"
    ),
    "discussion": (
        "Summarize the discussion: interpretation, stated limitations, and implications.\n"
        "Rules: facts only from the text; 'not reported' if absent. No outside info.\n\n"
    ),
    "conclusion": (
        "Summarize the conclusions in 2–4 factual sentences.\n"
        "Rules: facts only; 'not reported' if absent.\n\n"
    ),
    "full": (
        "Summarize the paper’s purpose, methods, main results, and key takeaways in factual sentences.\n"
        "Rules: ONLY facts; preserve numbers/units; use 'not reported' where missing; avoid repetition.\n\n"
    ),
}


ORDER = ["abstract","introduction","methods","results","discussion","conclusion","full"]

def _pick_synthesis_model(models):
    if "facebook/bart-large-cnn" in models:
        return "facebook/bart-large-cnn", models["facebook/bart-large-cnn"]
    mid = next(iter(models.keys()))
    return mid, models[mid]

def main():
    ap = argparse.ArgumentParser(description="Benchmark HF summarizers on PDFs (section-aware + synthesis).")
    ap.add_argument("--pdf", nargs="+", required=True, help="One or more PDF paths.")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="Model IDs.")
    ap.add_argument("--outdir", default="out", help="Output directory.")
    ap.add_argument("--structured", action="store_true",
                    help="If set, fallback full-summary uses a structured abstract prompt.")
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

    # --- Extract text from PDFs
    pdf_texts: Dict[Path, str] = {}
    for p in args.pdf:
        pdf = Path(p)
        if not pdf.exists():
            log(f"[WARN] Missing PDF: {pdf}")
            continue
        try:
            log(f"[INFO] Extracting: {pdf}")
            pdf_texts[pdf] = process_pdf(pdf)  # uses app.pdf_io + app.sections.stitch
            log(f"[OK] Extracted: {pdf}")
        except Exception as e:
            log(f"[ERROR] Failed to extract {pdf}: {e!r}")
            log(traceback.format_exc())
            continue

    if not pdf_texts:
        log("[FATAL] No valid PDFs processed. Aborting.")
        return

    # --- Load models
    models: Dict[str, Tuple] = {}
    for mid in args.models:
        try:
            log(f"[INFO] Loading model: {mid}")
            t0 = time.time()
            tok, model = load_model(mid, use_fast=args.use_fast_tokenizer)
            model.to(DEVICE)
            models[mid] = (tok, model)
            log(f"[OK] Loaded {mid} in {time.time()-t0:.1f}s")
        except Exception as e:
            log(f"[ERROR] Failed to load model {mid}: {e!r}")
            log(traceback.format_exc())

    if not models:
        log("[FATAL] No models loaded. Aborting.")
        return

    # --- Build report
    report_lines: List[str] = [
        "# IttyBitty Benchmark Report",
        f"- Structured: `{args.structured}`",
        f"- max_in_tokens: `{args.max_in_tokens}`, max_out_tokens: `{args.max_out_tokens}`, num_beams: `{args.num_beams}`",
        f"- Models: {', '.join(models.keys())}",
        ""
    ]

    # --- Run per PDF × model
    for pdf, full_text in pdf_texts.items():
        pdf_base = pdf.stem
        report_lines.append(f"## {pdf_base}")
        report_lines.append(f"_File_: `{pdf}`\n")

        for mid, (tok, model) in models.items():
            log(f"[RUN] {pdf_base} × {mid}")
            t0 = time.time()
            summary = ""  # ensure defined

            # 1) Split the full paper text into sections once per model
            secs = split_into_sections(full_text) or {"full": full_text}
            order = ["abstract","introduction","methods","results","discussion","conclusion","full"]

            parts: List[str] = []
            collected_for_synthesis: List[tuple[str, str]] = []   # <-- DEFINED HERE

            # 2) Summarize each available section
            for name in order:
                if name not in secs:
                    continue
                section_text = secs[name]
                prompt = SECTION_PROMPTS.get(name, SECTION_PROMPTS["full"])
                run_text = prompt + section_text

                log(f"[RUN] {pdf_base} × {mid} :: section={name} :: len={len(section_text)} chars")
                try:
                    section_summary = summarize_text_with(
                        tok, model, run_text,
                        structured=False,
                        max_in_tokens=args.max_in_tokens,
                        max_out_tokens=args.max_out_tokens,
                        num_beams=args.num_beams,
                    )
                    
                    # Section-aware filtering:
                    # - Results: require digits only if the source has digits; also keep modest overlap
                    # - Methods: keep modest overlap (to avoid general boilerplate)
                    # - Abstract/Introduction/Discussion/Conclusion: do NOT enforce overlap, just strip junk
                    has_numbers_in_source = bool(re.search(r"\d", section_text))

                    if name == "results":
                        section_summary = clean_and_verify(
                            section_summary, section_text,
                            min_overlap=0.15,
                            require_digit=has_numbers_in_source,   # only if the source actually has numbers
                            enforce_overlap=True
                        )
                    elif name == "methods":
                        section_summary = clean_and_verify(
                            section_summary, section_text,
                            min_overlap=0.15,
                            require_digit=False,
                            enforce_overlap=True
                        )
                    else:
                        section_summary = clean_and_verify(
                            section_summary, section_text,
                            min_overlap=0.0,
                            require_digit=False,
                            enforce_overlap=False
                        )

                except Exception as e:
                    section_summary = f"[ERROR] {e!r}"

                parts.append(f"### {name.title()}\n{section_summary}")

                # Only carry forward real content for synthesis
                if section_summary and section_summary != "not reported" and not section_summary.startswith("[ERROR]"):
                    collected_for_synthesis.append((name, section_summary))

            # 3) Second-pass synthesis from section summaries
            if collected_for_synthesis:
                # <-- COMBINED TEXT IS BUILT HERE
                combined_text = "\n".join(f"{n.title()}:\n{txt}" for n, txt in collected_for_synthesis)

                synth_id, (synth_tok, synth_model) = _pick_synthesis_model(models)
                synth_prompt = (
                    "Combine the section summaries into a single structured abstract with exactly these headers:\n"
                    "Background:\nMethods:\nResults:\nConclusions:\n\n"
                    "Rules: Use ONLY facts present in the summaries below. If a detail is missing, write 'not reported'. "
                    "Preserve numbers/units/statistics exactly as given. Avoid repetition.\n\n"
                )
                try:
                    synthesized = summarize_text_with(
                        synth_tok, synth_model, synth_prompt + combined_text,
                        structured=False,
                        max_in_tokens=args.max_in_tokens,
                        max_out_tokens=max(args.max_out_tokens, 384),
                        num_beams=max(args.num_beams, 4),
                    )
                    synthesized = clean_and_verify(synthesized, combined_text, min_overlap=0.25)
                except Exception as e:
                    synthesized = f"[ERROR] {e!r}"

                parts.append(f"### Synthesized (Second Pass via {synth_id})\n{synthesized}")

            # 4) Finalize per-model summary
            summary = "\n\n".join(parts)
            preview = summary[:600].replace("\n", " ")
            log(f"[OK] {pdf_base} × {mid} (SECTIONED) ({time.time()-t0:.1f}s) :: {preview}...")

            # write per-model text
            out_txt = outdir / f"{sanitize(pdf_base)}__{sanitize(mid)}.txt"
            try:
                out_txt.write_text(summary, encoding="utf-8")
            except Exception as e:
                log(f"[ERROR] Writing {out_txt}: {e!r}")

            # add to report
            report_lines += [f"### Model: `{mid}`", "```text", summary, "```", ""]

    # Write combined report
    report_md = outdir / "benchmark_report.md"
    try:
        report_md.write_text("\n".join(report_lines), encoding="utf-8")
        log(f"[OK] Wrote report: {report_md}")
        log(f"[OK] Individual outputs in: {outdir.resolve()}")
    except Exception as e:
        log(f"[ERROR] Writing report: {e!r}")

if __name__ == "__main__":
    main()
