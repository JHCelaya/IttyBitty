import fitz  # PyMuPDF

def extract_text_by_page(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    try:
        txt = "\n\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    return txt