#!/usr/bin/env python
"""
Multi-pass academic paper summarizer that extracts SPECIFIC information.

Pass 1: Extract structured facts
Pass 2: Generate readable summary using facts
Pass 3: Quality check and format
"""
from pathlib import Path
import sys
import re
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pdf_io import extract_text_by_page
from app.sections import split_into_sections
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Pass 1: Extract specific information
EXTRACTION_PROMPTS = {
    "abstract": {
        "research_question": "What research question or problem does this paper address? State it as a single specific question.",
        "approach": "What method or approach did they use? Include the key technique or framework.",
        "main_finding": "What is the single most important finding or conclusion? Be specific with numbers if mentioned.",
    },
    
    "introduction": {
        "gap": "What gap in existing knowledge does this paper address? What was unknown or unclear before?",
        "hypothesis": "What is the specific hypothesis or prediction they test?",
        "theoretical_framework": "What theory or framework do they build on? Name specific theories or models.",
    },
    
    "methods": {
        "participants": "Who/what was studied? Include: species, sample size (N=?), age, demographics, any inclusion criteria.",
        "design": "What was the experimental design? Include: independent/dependent variables, conditions, trial structure.",
        "procedure": "What did participants/subjects actually DO? Describe the task or procedure step-by-step.",
        "measures": "What was measured? Include: specific tests, questionnaires, imaging methods, behavioral measures.",
        "analysis": "What statistical analyses were used? Include: specific tests (t-test, ANOVA, regression), software used.",
    },
    
    "results": {
        "primary_finding": "What was the PRIMARY result? Include specific numbers: means, standard deviations, percentages.",
        "statistics": "What are the key statistics? Include: test values, p-values, effect sizes, confidence intervals.",
        "secondary_findings": "What other significant findings were reported? Include numbers.",
        "figures": "What do the main figures/tables show? Describe key patterns or trends.",
    },
    
    "discussion": {
        "interpretation": "How do the authors interpret their main finding? What do they think it means?",
        "mechanisms": "What mechanism or explanation do they propose?",
        "limitations": "What limitations do they acknowledge? Be specific.",
        "implications": "What are the practical or theoretical implications?",
        "future": "What future research do they suggest?",
    }
}

def extract_numbers(text: str) -> List[str]:
    """Extract all numbers with context from text."""
    # Pattern for: N=24, M=45.2, SD=8.1, p<.01, t(48)=3.2, d=0.78
    patterns = [
        r'[NnMm]\s*=\s*[\d.]+',
        r'SD\s*=\s*[\d.]+',
        r'[pt]\s*[<>=]\s*\.?\d+',
        r't\(\d+\)\s*=\s*[\d.]+',
        r'd\s*=\s*[\d.]+',
        r'r\s*=\s*[\d.]+',
        r'F\(\d+,\s*\d+\)\s*=\s*[\d.]+',
        r'\d+%',
        r'\d+\s*participants?',
        r'\d+\s*subjects?',
    ]
    
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    
    return list(set(found))

def extract_citations(text: str) -> List[str]:
    """Extract key citations from text."""
    # Pattern for: (Author, Year) or Author et al. (Year)
    patterns = [
        r'[A-Z][a-z]+(?:\s+et al\.)?\s*\(\d{4}\)',
        r'\([A-Z][a-z]+(?:\s+et al\.)?,?\s*\d{4}\)',
    ]
    
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        found.extend(matches)
    
    # Return most frequent (key citations)
    from collections import Counter
    counts = Counter(found)
    return [cite for cite, count in counts.most_common(5)]

def extract_fact(text: str, question: str, tokenizer, model) -> str:
    """Extract a specific fact from text using targeted question."""
    prompt = f"{question}\n\nAnswer in 1-2 specific sentences using ONLY information from the text below. Include numbers, names, and technical terms.\n\nTEXT:\n{text[:2000]}"
    
    enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
    enc = {k: v.to(DEVICE) for k, v in enc.items()}
    
    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=150,
            num_beams=4,
            temperature=0.3,
            do_sample=True,
            top_p=0.9,
        )
    
    answer = tokenizer.decode(out[0], skip_special_tokens=True)
    return answer.strip()

def summarize_paper_detailed(pdf_path: str) -> Dict:
    """Generate detailed, information-dense summary."""
    print(f"\n{'='*60}")
    print(f"Processing: {Path(pdf_path).stem}")
    print(f"{'='*60}\n")
    
    # Extract and split
    raw_text = extract_text_by_page(pdf_path)
    sections = split_into_sections(raw_text)
    valid_sections = {name: text for name, text in sections.items() if len(text) > 200}
    
    print(f"Found sections: {list(valid_sections.keys())}\n")
    
    # Load model
    print("Loading model...")
    MODEL_ID = "facebook/bart-large-cnn"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)
    model.to(DEVICE)
    model.eval()
    print("✓ Model loaded\n")
    
    # Pass 1: Extract structured facts
    print("Pass 1: Extracting facts...")
    extracted = {}
    
    for section_name, section_text in valid_sections.items():
        if section_name not in EXTRACTION_PROMPTS:
            continue
        
        print(f"  [{section_name}]")
        extracted[section_name] = {}
        
        questions = EXTRACTION_PROMPTS[section_name]
        for fact_name, question in questions.items():
            print(f"    - {fact_name}...", end=" ", flush=True)
            try:
                answer = extract_fact(section_text, question, tokenizer, model)
                extracted[section_name][fact_name] = answer
                print("✓")
            except Exception as e:
                print(f"✗ {e}")
                extracted[section_name][fact_name] = "not reported"
    
    # Pass 2: Extract numbers and citations
    print("\nPass 2: Extracting numbers and citations...")
    for section_name, section_text in valid_sections.items():
        if section_name == "methods" or section_name == "results":
            nums = extract_numbers(section_text)
            if nums:
                extracted[section_name]["key_numbers"] = nums
                print(f"  [{section_name}] Found {len(nums)} numbers: {nums[:5]}")
        
        if section_name == "introduction":
            cites = extract_citations(section_text)
            if cites:
                extracted[section_name]["key_citations"] = cites
                print(f"  [introduction] Key citations: {cites}")
    
    return extracted

def format_summary(extracted: Dict) -> str:
    """Format extracted facts into readable summary."""
    output = []
    
    # Abstract/Overview
    if "abstract" in extracted:
        abs_data = extracted["abstract"]
        output.append("## Overview\n")
        output.append(f"**Research Question**: {abs_data.get('research_question', 'not reported')}\n")
        output.append(f"**Approach**: {abs_data.get('approach', 'not reported')}\n")
        output.append(f"**Main Finding**: {abs_data.get('main_finding', 'not reported')}\n")
    
    # Introduction
    if "introduction" in extracted:
        intro = extracted["introduction"]
        output.append("## Background\n")
        output.append(f"**Knowledge Gap**: {intro.get('gap', 'not reported')}\n")
        output.append(f"**Hypothesis**: {intro.get('hypothesis', 'not reported')}\n")
        output.append(f"**Theoretical Framework**: {intro.get('theoretical_framework', 'not reported')}\n")
        
        if "key_citations" in intro:
            output.append(f"**Key Citations**: {', '.join(intro['key_citations'][:5])}\n")
    
    # Methods
    if "methods" in extracted:
        meth = extracted["methods"]
        output.append("## Methods\n")
        output.append(f"**Participants/Sample**: {meth.get('participants', 'not reported')}\n")
        output.append(f"**Design**: {meth.get('design', 'not reported')}\n")
        output.append(f"**Procedure**: {meth.get('procedure', 'not reported')}\n")
        output.append(f"**Measures**: {meth.get('measures', 'not reported')}\n")
        output.append(f"**Analysis**: {meth.get('analysis', 'not reported')}\n")
        
        if "key_numbers" in meth:
            output.append(f"**Key Numbers**: {', '.join(meth['key_numbers'][:10])}\n")
    
    # Results
    if "results" in extracted:
        res = extracted["results"]
        output.append("## Results\n")
        output.append(f"**Primary Finding**: {res.get('primary_finding', 'not reported')}\n")
        output.append(f"**Statistics**: {res.get('statistics', 'not reported')}\n")
        
        if "key_numbers" in res:
            output.append(f"**Key Data**: {', '.join(res['key_numbers'][:10])}\n")
        
        secondary = res.get('secondary_findings', '')
        if secondary and secondary != 'not reported':
            output.append(f"**Secondary Findings**: {secondary}\n")
    
    # Discussion
    if "discussion" in extracted:
        disc = extracted["discussion"]
        output.append("## Discussion\n")
        output.append(f"**Interpretation**: {disc.get('interpretation', 'not reported')}\n")
        output.append(f"**Limitations**: {disc.get('limitations', 'not reported')}\n")
        output.append(f"**Implications**: {disc.get('implications', 'not reported')}\n")
    
    return "\n".join(output)

def main():
    import argparse
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--output", default="detailed_summary.md")
    args = ap.parse_args()
    
    # Extract
    extracted = summarize_paper_detailed(args.pdf)
    
    # Format
    print("\nFormatting summary...")
    summary = format_summary(extracted)
    
    # Add header
    final = [
        f"# Detailed Summary: {Path(args.pdf).stem}",
        f"_Information-Dense Academic Summary_\n",
        "---\n",
        summary
    ]
    
    # Save
    Path(args.output).write_text("\n".join(final))
    print(f"\n✓ Saved to: {args.output}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()