#!/usr/bin/env python
"""
Debug script to see what's in the PDF and why section detection fails.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pdf_io import extract_text_by_page
from app.sections import split_into_sections
import re

def show_potential_headers(text: str, max_lines: int = 100):
    """Find lines that might be section headers."""
    print("\n" + "="*60)
    print("POTENTIAL SECTION HEADERS IN PDF:")
    print("="*60)
    
    # Look for lines that are all caps or title case
    patterns = [
        (r'^([A-Z][A-Z\s&/\-]{2,50})$', "ALL CAPS"),
        (r'^(\d+\.?\s*[A-Z][A-Za-z\s&/\-]{2,50})$', "NUMBERED"),
        (r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})$', "TITLE CASE"),
    ]
    
    lines = text.split('\n')
    found = []
    
    for i, line in enumerate(lines[:max_lines]):
        line = line.strip()
        if not line or len(line) < 5:
            continue
            
        for pattern, label in patterns:
            if re.match(pattern, line):
                found.append((i, line, label))
                break
    
    if found:
        for line_num, line, label in found[:30]:  # Show first 30 matches
            print(f"Line {line_num:4d} [{label:12s}]: {line}")
    else:
        print("No potential headers found!")
    
    print(f"\nTotal potential headers: {len(found)}")

def show_first_chars(text: str, n: int = 2000):
    """Show the beginning of the text."""
    print("\n" + "="*60)
    print(f"FIRST {n} CHARACTERS OF PDF:")
    print("="*60)
    print(text[:n])
    print("...")

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_sections.py <path_to_pdf>")
        print('Example: python debug_sections.py "C:\\path\\to\\paper.pdf"')
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    print(f"Analyzing: {pdf_path}")
    
    # Extract text
    try:
        text = extract_text_by_page(pdf_path)
        print(f"\nTotal length: {len(text)} characters")
        print(f"Total lines: {len(text.splitlines())}")
    except Exception as e:
        print(f"ERROR extracting text: {e}")
        return
    
    # Show beginning of text
    show_first_chars(text, 2000)
    
    # Show potential headers
    show_potential_headers(text, 200)
    
    # Try section detection
    print("\n" + "="*60)
    print("SECTION DETECTION RESULTS:")
    print("="*60)
    sections = split_into_sections(text)
    
    for name, content in sections.items():
        preview = content[:100].replace('\n', ' ')
        print(f"\n[{name}] - {len(content)} chars")
        print(f"  Preview: {preview}...")
    
    # Save full output for inspection
    output_file = Path("debug_output.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("FULL EXTRACTED TEXT:\n")
        f.write("="*60 + "\n")
        f.write(text)
        f.write("\n\n" + "="*60 + "\n")
        f.write("DETECTED SECTIONS:\n")
        f.write("="*60 + "\n")
        for name, content in sections.items():
            f.write(f"\n### {name.upper()} ###\n")
            f.write(content)
            f.write("\n\n")
    
    print(f"\n✓ Full output saved to: {output_file}")

if __name__ == "__main__":
    main()