"""
Free Version - Uses Hugging Face API
Works on Mac, PC, Linux
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import json
import httpx
from datetime import datetime
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pdf_io import extract_text_by_page
from app.sections import split_into_sections

app = FastAPI(title="Paper Summarizer - Free")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PAPERS_FILE = DATA_DIR / "papers.json"

HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
# Updated API URL - Hugging Face changed their endpoint
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

if not PAPERS_FILE.exists():
    PAPERS_FILE.write_text("[]")

# Prompts - THESE ARE THE KEY TO QUALITY
SECTION_PROMPTS = {
    "abstract": """
Extract from this abstract:
1. Main research question (one sentence)
2. Method used (one sentence)  
3. Primary finding with numbers if mentioned (one sentence)

Format as 3 clear sentences. Use ONLY information from the text.

ABSTRACT:
""",
    
    "introduction": """
Answer these questions from this introduction:
- What research question does this address?
- What theoretical framework do they use? (name specific theories/models)
- What gap in knowledge exists?

Write 3 factual sentences with specific names and theories.

INTRODUCTION:
""",
    
    "methods": """
Extract these details from the methods section:

PARTICIPANTS: [Who/what was studied? Include N=, species, demographics]
DESIGN: [Experimental design with variables]
PROCEDURE: [What did participants do?]
MEASURES: [What was measured?]
ANALYSIS: [Statistical tests]

Write as one paragraph with all these details. Use "not reported" if missing.

METHODS:
""",
    
    "results": """
Extract from the results:

PRIMARY RESULT: [Main finding with specific numbers: M=, SD=, %, etc.]
STATISTICS: [Test type, test value, p-value, effect size if given]
SECONDARY: [Other significant findings with numbers]

Write as 2-4 sentences including ALL numbers mentioned.

RESULTS:
""",
    
    "discussion": """
From this discussion section, extract:

INTERPRETATION: How do authors explain the findings?
LIMITATIONS: What limitations do they state?
IMPLICATIONS: What are the theoretical or practical implications?

Write 3 sentences covering these three points.

DISCUSSION:
""",
    
    "conclusion": """
State the main conclusion in 1-2 clear sentences. What is the key takeaway?

CONCLUSION:
"""
}

def load_papers():
    return json.loads(PAPERS_FILE.read_text())

def save_papers(papers):
    PAPERS_FILE.write_text(json.dumps(papers, indent=2))

def generate_paper_id():
    return f"paper_{int(datetime.now().timestamp() * 1000)}"

async def call_huggingface(text: str) -> str:
    """
    Use Hugging Face official client library.
    Simplified - no parameters argument.
    """
    if not HF_API_KEY:
        return "ERROR: Hugging Face API key not configured"
    
    try:
        # Import here to avoid loading if not needed
        from huggingface_hub import InferenceClient
        
        # Create client
        client = InferenceClient(token=HF_API_KEY)
        
        # Limit input length
        text = text[:3000]
        
        print(f"Calling HF with text length: {len(text)}")
        
        # Call summarization - no parameters argument!
        result = client.summarization(
            text,
            model="facebook/bart-large-cnn"
        )
        
        # Extract text from result
        if isinstance(result, dict):
            summary = result.get("summary_text", "")
        elif isinstance(result, str):
            summary = result
        else:
            summary = str(result)
        
        print(f"Got summary: {len(summary)} chars")
        return summary
        
    except ImportError:
        return "ERROR: Please install: pip install huggingface-hub"
    except Exception as e:
        print(f"HF Client Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return f"ERROR: {str(e)}"

def clean_summary(text: str) -> str:
    """Remove common artifacts."""
    if not text or text.startswith("ERROR") or text == "MODEL_LOADING":
        return text
    
    # Remove prompt echoes
    junk_phrases = [ 
        "extract from", "answer these", "write as", "format as",
        "use only", "from this", "section:", "abstract:", "introduction:",
        "methods:", "results:", "discussion:", "conclusion:"
    ]
    
    for phrase in junk_phrases:
        text = text.replace(phrase, "")
        text = text.replace(phrase.title(), "")
        text = text.replace(phrase.upper(), "")
    
    # Clean whitespace
    text = " ".join(text.split())
    
    return text.strip()

async def process_paper_background(paper_id: str, pdf_path: str):
    """Background processing."""
    try:
        print(f"[{paper_id}] Starting processing...")
        
        # Extract text
        raw_text = extract_text_by_page(pdf_path)
        print(f"[{paper_id}] Extracted {len(raw_text)} chars")
        
        # Split sections
        sections = split_into_sections(raw_text)
        valid_sections = {name: text for name, text in sections.items() if len(text) > 200}
        print(f"[{paper_id}] Found sections: {list(valid_sections.keys())}")
        
        # Summarize each
        summaries = {}
        for name in ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]:
            if name not in valid_sections:
                continue
            
            print(f"[{paper_id}] Processing {name}...")
            
            prompt = SECTION_PROMPTS[name]
            section_text = valid_sections[name]
            
            # Combine prompt and text
            full_text = prompt + "\n" + section_text
            
            # Call API
            summary = await call_huggingface(full_text)
            
            # Handle errors
            if summary == "MODEL_LOADING":
                print(f"[{paper_id}] Model loading, will retry...")
                # Wait and retry once
                import asyncio
                await asyncio.sleep(20)
                summary = await call_huggingface(full_text)
            
            if summary.startswith("ERROR"):
                print(f"[{paper_id}] Error on {name}: {summary}")
                summaries[name] = "Processing failed. Please try again."
                continue
            
            # Clean
            summary = clean_summary(summary)
            
            if len(summary.split()) >= 10:
                summaries[name] = summary
                print(f"[{paper_id}] ✓ {name} ({len(summary)} chars)")
            else:
                print(f"[{paper_id}] ✗ {name} too short")
        
        # Save
        papers = load_papers()
        for paper in papers:
            if paper["id"] == paper_id:
                paper["status"] = "complete"
                paper["sections"] = summaries
                break
        save_papers(papers)
        
        print(f"[{paper_id}] Complete! Generated {len(summaries)} summaries")
        
    except Exception as e:
        print(f"[{paper_id}] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        
        papers = load_papers()
        for paper in papers:
            if paper["id"] == paper_id:
                paper["status"] = "failed"
                paper["error"] = str(e)
                break
        save_papers(papers)
    
    finally:
        Path(pdf_path).unlink(missing_ok=True)

# Routes
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Paper Summarizer - Free Version",
        "model": "facebook/bart-large-cnn via Hugging Face",
        "hf_key_configured": bool(HF_API_KEY)
    }

@app.post("/api/upload")
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files")
    
    # Save temp
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    # Create record
    paper_id = generate_paper_id()
    title = Path(file.filename).stem
    
    paper_data = {
        "id": paper_id,
        "title": title,
        "filename": file.filename,
        "upload_date": datetime.now().isoformat(),
        "status": "processing",
        "sections": None
    }
    
    papers = load_papers()
    papers.append(paper_data)
    save_papers(papers)
    
    # Process
    background_tasks.add_task(process_paper_background, paper_id, tmp_path)
    
    return {
        "paper_id": paper_id,
        "status": "processing",
        "message": "Processing... Check status in 1-2 minutes"
    }

@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str):
    papers = load_papers()
    for paper in papers:
        if paper["id"] == paper_id:
            return paper
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/api/papers")
def list_papers():
    return load_papers()

@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str):
    papers = load_papers()
    papers = [p for p in papers if p["id"] != paper_id]
    save_papers(papers)
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("Paper Summarizer - Free Version")
    print("="*60)
    if not HF_API_KEY:
        print("⚠️  WARNING: HUGGINGFACE_API_KEY not set!")
        print("   Get key: https://huggingface.co/settings/tokens")
        print("   Then: export HUGGINGFACE_API_KEY='hf_xxxxx'")
    else:
        print("✓ Hugging Face API key configured")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)