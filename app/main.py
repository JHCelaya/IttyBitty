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
