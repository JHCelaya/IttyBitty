from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import os, tempfile

from .summarizer import summarize_text
from .pdf_io import extract_text_by_page
from .sections import split_into_sections, stitch_sections