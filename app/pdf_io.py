import re, fitz

def extract_text_by_page(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    try:
        raw = "\n\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()

    # de-hyphenate line breaks and normalize spaces/newlines
    raw = raw.replace("-\n", "")                  # join hyphenated words
    raw = re.sub(r"(?<=\w)\n(?=\w)", " ", raw)    # fix broken words at EOL
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    # drop common headers/footers/page numbers (tweak as needed)
    raw = re.sub(r"\n?Page \d+ of \d+\n?", "\n", raw, flags=re.I)
    raw = re.sub(r"\n?\b\d{1,3}\b\n", "\n", raw)  # lone page numbers
    return raw.strip()
