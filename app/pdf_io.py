import re, fitz

def extract_text_by_page(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    try:
        raw = "\n\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()

    # Drop references/bibliography (heuristic)
    raw = re.split(r"\nreferences?\b|\nbibliograph(y|ies)\b", raw, flags=re.I)[0]
    
    # Remove figure/table captions (heuristic)
    raw = re.sub(r"\n(Figure|Fig\.|Table)\s+\d+.*\n", "\n", raw)

    # de-hyphenate line breaks and normalize spaces/newlines
    raw = raw.replace("-\n", "")                  # join hyphenated words
    raw = re.sub(r"(?<=\w)\n(?=\w)", " ", raw)    # fix broken words at EOL
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    # drop common headers/footers/page numbers (tweak as needed)
    raw = re.sub(r"\n?Page \d+ of \d+\n?", "\n", raw, flags=re.I)
    raw = re.sub(r"\n?\b\d{1,3}\b\n", "\n", raw)  # lone page numbers
    return raw.strip()


