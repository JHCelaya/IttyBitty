Scientific Paper Summarizer
A web application that automatically generates structured summaries of academic papers using AI.
Features

📄 PDF Upload - Drag and drop any scientific paper
🤖 AI Summarization - Extracts key information from each section
📊 Structured Output - Abstract, Introduction, Methods, Results, Discussion, Conclusion
💾 Paper Library - Save and revisit previous summaries
🌐 Cross-Platform - Works on Mac, PC, Linux, and cloud deployments

Quick Start
1. Install Dependencies
bashpip install -r requirements.txt
2. Get API Key (Free)

Go to Hugging Face
Create a new token
Copy the token (starts with hf_)

3. Set Environment Variable
Mac/Linux:
bashexport HUGGINGFACE_API_KEY="hf_your_token_here"
Windows:
powershell$env:HUGGINGFACE_API_KEY="hf_your_token_here"
4. Run the App
bashpython app/main_free.py
Then open frontend.html in your browser!
How It Works
PDF Upload → Text Extraction → Section Detection → AI Summarization → Display

Upload: User uploads PDF via web interface
Extract: PyMuPDF extracts text from PDF
Split: Custom regex patterns identify paper sections
Summarize: Hugging Face API (BART model) generates summaries
Store: Results saved locally in JSON format
Display: Frontend shows structured summary

Project Structure
IttyBitty/
├── app/
│   ├── main_free.py       # FastAPI backend (production)
│   ├── pdf_io.py          # PDF text extraction
│   └── sections.py        # Section detection
├── scripts/
│   ├── benchmark.py       # Test different models
│   ├── summarize.py       # Standalone CLI tool
│   └── check_sections.py  # Debug section detection
├── data/
│   └── papers.json        # Paper database
├── frontend.html          # Web interface
└── requirements.txt       # Python dependencies
Configuration
Edit app/main_free.py to adjust:
Summary Quality
pythonSECTION_PROMPTS = {
    "methods": """Your custom prompt here..."""
}
API Parameters
python"parameters": {
    "max_length": 300,      # Longer = more detail
    "min_length": 80,       # Force minimum content
    "num_beams": 4,         # Higher = better quality
}