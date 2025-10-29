Scientific-Summarizer

A lightweight FastAPI backend that summarizes scientific papers (PDFs or raw text) using Hugging Face transformer models.
The app is designed for research workflows: it outputs structured abstracts (Background, Methods, Results, Conclusions) to improve clarity and reduce hallucinations.

Features

- Text endpoint → summarize any pasted text.

- PDF endpoint → upload a journal article and get a structured abstract.

- Scientific-domain models (e.g. pegasus-pubmed, pegasus-arxiv, allenai/led-base-16384).

- Section-aware parsing → attempts to split Intro/Methods/Results/Discussion before summarizing.

- Hierarchical chunking → handles long papers by summarizing in pieces, then combining

python -m scripts.benchmark --pdf "C:/Users/jackc/OneDrive/Desktop/Notes/1 - Source Material/Daniela Schiller - 2015.pdf" `
  --models google/flan-t5-large facebook/bart-large-cnn google/pegasus-pubmed `
  --structured --max_out_tokens 512 --num_beams 4
