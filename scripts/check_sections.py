#!/usr/bin/env python
"""Quick script to see what sections were found and their sizes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pdf_io import extract_text_by_page
from app.sections import split_into_sections

if len(sys.argv) < 2:
    print("Usage: python check_sections.py <pdf_path>")
    sys.exit(1)

pdf_path = sys.argv[1]
print(f"\nAnalyzing: {pdf_path}\n")

# Extract and split
raw = extract_text_by_page(pdf_path)
sections = split_into_sections(raw)

print(f"Total text: {len(raw)} chars")
print(f"Sections found: {len(sections)}\n")

for name, text in sections.items():
    preview = text[:150].replace('\n', ' ')
    print(f"[{name.upper()}] - {len(text)} chars")
    print(f"  Preview: {preview}...")
    print()
