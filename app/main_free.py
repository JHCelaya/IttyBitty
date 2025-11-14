"""
Universal Academic Primer Version
Works for ANY type of academic paper - no section splitting
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import json
from datetime import datetime
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pdf_io import extract_text_by_page
# NOTE: We're NOT importing split_into_sections anymore!

app = FastAPI(title="Paper Summarizer - Universal Primer")

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Use OpenAI if available, fallback to HF
USE_OPENAI = bool(OPENAI_API_KEY)

if not PAPERS_FILE.exists():
    PAPERS_FILE.write_text("[]")

# ============================================================================
# IMPROVED MULTI-PASS PROMPT SYSTEM
# ============================================================================

# Pass 1: Extract concrete facts
FACT_EXTRACTION_PROMPT = """
Extract specific, concrete facts from this academic paper.

For each category, provide SPECIFIC details (not vague descriptions):

**KEY TERMS & CONCEPTS**
List 5-7 important terms/concepts with brief definitions. Example: "Time cells - hippocampal neurons that fire at specific moments rather than locations"

**SPECIFIC FINDINGS**
List 3-5 concrete findings with details. Include numbers, measurements, or specific examples where mentioned.

**NAMED THEORIES/FRAMEWORKS**
What specific theories, models, or frameworks are discussed? Include author names and years.

**STUDY DETAILS** (if applicable)
- Sample: Who/what was studied? Include N=, species, demographics
- Methods: What specific techniques or procedures?
- Data: What specific measurements or analyses?

**CONCRETE EXAMPLES**
What specific examples, cases, or illustrations are given?

Be SPECIFIC. Avoid phrases like "various aspects" or "the authors discuss". Include names, numbers, technical terms.

PAPER TEXT:
{text}

EXTRACTED FACTS:"""

# Pass 2: Build the narrative
NARRATIVE_SYNTHESIS_PROMPT = """
Using ONLY the facts extracted below, create a comprehensive primer for readers.

EXTRACTED FACTS:
{facts}

Create a primer with these sections:

**🎯 ONE-SENTENCE SUMMARY**
[Max 30 words - capture the core argument with specific details]

**📖 THE ARGUMENT IN PLAIN LANGUAGE**
[3-4 sentences explaining the main claim. Use specific terms from the facts above. Make it concrete and vivid.]

**💡 WHY THIS MATTERS**
[2-3 sentences on significance. What changes? What's new? Be specific about impact.]

**🔬 THE EVIDENCE**
[4-5 sentences describing how they support their claim. Include:
- Specific methods or approaches
- Key findings with details from the facts
- Concrete examples
Use bullet points if it helps clarity]

**✨ KEY INSIGHTS** 
[4-5 bullet points of takeaways. Each should be:
- Specific (include terms, numbers, names)
- Actionable or memorable
- Something a reader will remember]

**🎓 BOTTOM LINE**
[2-3 sentences: What's the conclusion? What are implications? Who benefits?]

**👥 FOR READERS IN**
[List specific fields, roles, or interests this serves]

CRITICAL RULES:
- Use SPECIFIC terms and details from the facts
- No vague language ("various", "explores", "discusses")
- Include names, numbers, technical terms
- Make it vivid and concrete
- Write for an intelligent reader who doesn't know the field

PRIMER:"""

# ============================================================================
# API CALL FUNCTION
# ============================================================================

async def call_openai(text: str) -> str:
    """Call OpenAI GPT-3.5 - Fast, reliable, cheap ($0.002/paper)."""
    if not OPENAI_API_KEY:
        return "ERROR: OpenAI API key not configured"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        print(f"Calling OpenAI with {len(text)} chars...")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert at creating clear, structured summaries of academic papers."},
                {"role": "user", "content": text}
            ],
            max_tokens=800,
            temperature=0.3
        )
        
        result = response.choices[0].message.content
        print(f"Got result: {len(result)} chars")
        return result
        
    except ImportError:
        return "ERROR: Please install: pip install openai"
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return f"ERROR: {str(e)}"

async def call_huggingface(text: str) -> str:
    """Call Hugging Face API using summarization (most reliable)."""
    if not HF_API_KEY:
        return "ERROR: Hugging Face API key not configured"
    
    try:
        from huggingface_hub import InferenceClient
        
        client = InferenceClient(token=HF_API_KEY)
        
        print(f"Calling HF with {len(text)} chars...")
        
        # Use summarization - it's the most stable endpoint
        result = client.summarization(
            text,
            model="facebook/bart-large-cnn"
        )
        
        # Extract text from result
        if isinstance(result, dict):
            summary = result.get("summary_text", str(result))
        elif isinstance(result, str):
            summary = result
        else:
            summary = str(result)
        
        print(f"Got result: {len(summary)} chars")
        return summary
        
    except ImportError:
        return "ERROR: Please install: pip install huggingface-hub"
    except Exception as e:
        print(f"HF Error: {e}")
        return f"ERROR: {str(e)}"

async def generate_primer(text: str) -> str:
    """Generate primer using best available API."""
    if USE_OPENAI:
        return await call_openai(text)
    else:
        return await call_huggingface(text)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_papers():
    return json.loads(PAPERS_FILE.read_text())

def save_papers(papers):
    PAPERS_FILE.write_text(json.dumps(papers, indent=2))

def generate_paper_id():
    return f"paper_{int(datetime.now().timestamp() * 1000)}"

def clean_primer(text: str) -> str:
    """Clean up the generated primer."""
    if not text or text.startswith("ERROR"):
        return text
    
    # Remove common artifacts
    text = text.strip()
    
    # Ensure it starts with content, not the prompt
    if text.startswith("**ONE-SENTENCE SUMMARY**"):
        return text
    
    # If it includes the prompt, remove it
    if "PAPER TEXT" in text:
        text = text.split("PAPER TEXT")[0]
    
    return text.strip()

# ============================================================================
# BACKGROUND PROCESSING
# ============================================================================

async def process_paper_background(paper_id: str, pdf_path: str):
    """Generate universal primer using smart sampling from full paper."""
    try:
        print(f"\n[{paper_id}] Starting processing...")
        
        # Step 1: Extract full text
        raw_text = extract_text_by_page(pdf_path)
        print(f"[{paper_id}] Extracted {len(raw_text)} characters")
        
        # Step 2: Smart sampling - take from beginning, middle, end
        total_len = len(raw_text)
        
        # Beginning: Abstract, intro (0-3000)
        beginning = raw_text[:3000]
        
        # Middle: Methods, results (from 30-60% through paper)
        middle_start = int(total_len * 0.3)
        middle_end = int(total_len * 0.6)
        middle = raw_text[middle_start:middle_start + 3000]
        
        # End: Discussion, conclusion (last 3000 chars)
        end = raw_text[-3000:] if total_len > 3000 else ""
        
        # Combine with markers
        text_sample = f"""
=== BEGINNING (Abstract & Introduction) ===
{beginning}

=== MIDDLE (Core Content) ===
{middle}

=== END (Discussion & Conclusion) ===
{end}
"""
        
        print(f"[{paper_id}] Created sample: {len(text_sample)} chars from full paper")
        
        # PASS 1: Extract concrete facts
        print(f"[{paper_id}] Pass 1: Extracting facts...")
        fact_prompt = FACT_EXTRACTION_PROMPT.format(text=text_sample)
        facts = await generate_primer(fact_prompt)
        
        if facts.startswith("ERROR"):
            print(f"[{paper_id}] Fact extraction failed: {facts}")
            raise Exception(facts)
        
        print(f"[{paper_id}] Extracted {len(facts)} chars of facts")
        
        # PASS 2: Synthesize into primer
        print(f"[{paper_id}] Pass 2: Synthesizing primer...")
        synthesis_prompt = NARRATIVE_SYNTHESIS_PROMPT.format(facts=facts)
        primer = await generate_primer(synthesis_prompt)
        
        if primer.startswith("ERROR"):
            print(f"[{paper_id}] Synthesis failed: {primer}")
            raise Exception(primer)
        
        # Step 3: Clean up
        primer = clean_primer(primer)
        
        print(f"[{paper_id}] Generated {len(primer)} characters")
        
        # Step 4: Save results
        papers = load_papers()
        for paper in papers:
            if paper["id"] == paper_id:
                paper["status"] = "complete"
                paper["primer"] = primer
                paper["facts"] = facts  # Save facts too for debugging
                paper["sections"] = {"primer": primer}  # Backwards compat
                break
        save_papers(papers)
        
        print(f"[{paper_id}] ✓ Complete!")
        
    except Exception as e:
        print(f"[{paper_id}] Error: {e}")
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

# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/")
def root():
    api_provider = "OpenAI GPT-3.5" if USE_OPENAI else "Hugging Face BART"
    return {
        "status": "ok",
        "message": "Universal Academic Primer",
        "approach": "Single comprehensive primer (no section splitting)",
        "api_provider": api_provider,
        "openai_configured": bool(OPENAI_API_KEY),
        "hf_configured": bool(HF_API_KEY)
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
        "primer": None,
        "sections": None  # For backwards compatibility
    }
    
    papers = load_papers()
    papers.append(paper_data)
    save_papers(papers)
    
    # Process
    background_tasks.add_task(process_paper_background, paper_id, tmp_path)
    
    return {
        "paper_id": paper_id,
        "status": "processing",
        "message": "Generating primer... Check status in 30-60 seconds"
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
    print("Universal Academic Primer")
    print("="*60)
    
    if OPENAI_API_KEY:
        print("✓ Using OpenAI GPT-3.5 (best quality)")
        print("  Cost: ~$0.002 per paper")
    elif HF_API_KEY:
        print("✓ Using Hugging Face BART (free but limited)")
        print("⚠️  For better quality, set OPENAI_API_KEY")
    else:
        print("❌ No API keys configured!")
        print("  Option 1: OpenAI (best) - https://platform.openai.com/api-keys")
        print("  Option 2: HuggingFace (free) - https://huggingface.co/settings/tokens")
    
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)