from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import os, tempfile

from .summarizer import summarize_text
from .pdf_io import extract_text_by_page
from .sections import split_into_sections, stitch_sections

app = FastAPI(title="ittybitty")

class TextIn(BaseModel):
    text: str

@app.post("/summarize-text")
def summarize_text_endpoint(payload: TextIn):
    try:
        return {"summary": summarize_text(payload.text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize-pdf")
async def summarize_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        raw_text = extract_text_by_page(tmp_path)
        sections = split_into_sections(raw_text)
        stitched = stitch_sections(sections)
        return {"summary": summarize_text(stitched or raw_text)}
    finally:
        os.remove(tmp_path)