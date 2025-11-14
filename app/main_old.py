"""
FastAPI backend for Scientific Paper Summarizer
Handles PDF upload, summarization, and storage
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import tempfile
import time
from datetime import datetime
from typing import List, Optional
import json

# Initialize FastAPI
app = FastAPI(title="Scientific Paper Summarizer API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PAPERS_FILE = DATA_DIR / "papers.json"

# Initialize papers database
if not PAPERS_FILE.exists():
    PAPERS_FILE.write_text("[]")

# Models
class PaperSummary(BaseModel):
    id: str
    title: str
    filename: str
    upload_date: str
    sections: dict
    model: str

class SummaryResponse(BaseModel):
    success: bool
    paper_id: str
    title: str
    sections: dict

# Helper functions
def load_papers() -> List[dict]:
    """Load papers from JSON file."""
    return json.loads(PAPERS_FILE.read_text())

def save_papers(papers: List[dict]):
    """Save papers to JSON file."""
    PAPERS_FILE.write_text(json.dumps(papers, indent=2))

def generate_paper_id() -> str:
    """Generate unique paper ID."""
    return f"paper_{int(time.time() * 1000)}"

def summarize_pdf(pdf_path: str) -> dict:
    """
    Summarize a PDF file.
    Returns dict with sections.
    """
    from app.pdf_io import extract_text_by_page
    from app.sections import split_into_sections
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    
    # Extract text
    raw_text = extract_text_by_page(pdf_path)
    sections = split_into_sections(raw_text)
    
    # Filter valid sections
    valid_sections = {
        name: text for name, text in sections.items() 
        if len(text) > 200
    }
    
    if not valid_sections:
        raise ValueError("No valid sections found in PDF")
    
    # Load model (cache this in production!)
    MODEL_ID = "facebook/bart-large-cnn"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)
    model.to(device)
    model.eval()
    
    # Section prompts
    PROMPTS = {
        "abstract": "Summarize this abstract in 2-3 sentences covering the research question and main findings.\n\n",
        "introduction": "What is the main research question or gap being addressed? (2-3 sentences)\n\n",
        "methods": "Describe the participants/subjects, design, and main procedures. (2-4 sentences)\n\n",
        "results": "What were the main findings? Include specific data if mentioned. (2-4 sentences)\n\n",
        "discussion": "How do the authors interpret the findings? What are limitations and implications? (2-3 sentences)\n\n",
        "conclusion": "Summarize the main conclusions. (1-2 sentences)\n\n",
    }
    
    # Summarize each section
    summaries = {}
    for name in ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]:
        if name not in valid_sections:
            continue
        
        section_text = valid_sections[name]
        prompt = PROMPTS.get(name, "Summarize this section.\n\n")
        full_text = prompt + section_text
        
        # Tokenize and generate
        enc = tokenizer(full_text, return_tensors="pt", truncation=True, max_length=1024)
        enc = {k: v.to(device) for k, v in enc.items()}
        
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=256,
                min_new_tokens=50,
                num_beams=6,
                length_penalty=1.2,
                no_repeat_ngram_size=4,
                repetition_penalty=1.3,
            )
        
        summary = tokenizer.decode(out[0], skip_special_tokens=True)
        
        # Clean up
        summary = summary.strip()
        if len(summary.split()) >= 10:
            summaries[name] = summary
    
    return summaries

# Routes
@app.get("/")
def root():
    """API health check."""
    return {"status": "ok", "message": "Scientific Paper Summarizer API"}

@app.post("/api/upload", response_model=SummaryResponse)
async def upload_paper(file: UploadFile = File(...)):
    """
    Upload and summarize a PDF.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Summarize
        sections = summarize_pdf(tmp_path)
        
        # Generate paper ID and metadata
        paper_id = generate_paper_id()
        title = Path(file.filename).stem
        
        # Save to database
        papers = load_papers()
        paper_data = {
            "id": paper_id,
            "title": title,
            "filename": file.filename,
            "upload_date": datetime.now().isoformat(),
            "sections": sections,
            "model": "facebook/bart-large-cnn"
        }
        papers.append(paper_data)
        save_papers(papers)
        
        return SummaryResponse(
            success=True,
            paper_id=paper_id,
            title=title,
            sections=sections
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
    
    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)

@app.get("/api/papers", response_model=List[PaperSummary])
def list_papers():
    """
    Get list of all summarized papers.
    """
    papers = load_papers()
    return papers

@app.get("/api/papers/{paper_id}", response_model=PaperSummary)
def get_paper(paper_id: str):
    """
    Get a specific paper by ID.
    """
    papers = load_papers()
    for paper in papers:
        if paper["id"] == paper_id:
            return paper
    raise HTTPException(status_code=404, detail="Paper not found")

@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str):
    """
    Delete a paper.
    """
    papers = load_papers()
    papers = [p for p in papers if p["id"] != paper_id]
    save_papers(papers)
    return {"success": True, "message": "Paper deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)