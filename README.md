Scientific-Summarizer

A lightweight FastAPI backend that summarizes scientific papers (PDFs or raw text) using Hugging Face transformer models.
The app is designed for research workflows: it outputs structured abstracts (Background, Methods, Results, Conclusions) to improve clarity and reduce hallucinations.

Features

- Text endpoint → summarize any pasted text.

- PDF endpoint → upload a journal article and get a structured abstract.

- Scientific-domain models (e.g. pegasus-pubmed, pegasus-arxiv, allenai/led-base-16384).

- Section-aware parsing → attempts to split Intro/Methods/Results/Discussion before summarizing.

- Hierarchical chunking → handles long papers by summarizing in pieces, then combining