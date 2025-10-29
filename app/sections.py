import re

SECTION_ALIASES = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background"],
    "methods": [
        "methods", "materials and methods", "materials & methods",
        "method", "participants", "procedure", "procedures",
        "experimental procedures", "participants and methods",
    ],
    "results": ["results", "findings", "results and discussion"],
    "discussion": ["discussion", "general discussion"],
    "conclusion": ["conclusion", "conclusions", "concluding remarks", "summary and conclusions"],
}

EXCLUDE_ALIASES = {
    "references", "bibliography", "acknowledgments", "acknowledgements",
    "supplement", "supplementary", "appendix", "author contributions",
    "funding", "conflict of interest", "competing interests",
}

ORDER = ["abstract", "introduction", "methods", "results", "discussion", "conclusion", "full"]

def _canon(key: str) -> str:
    k = key.strip().lower().strip(":.;,- ")
    for canon, aliases in SECTION_ALIASES.items():
        if k == canon or k in aliases:
            return canon
        if any(k.startswith(a) or a in k for a in [canon, *aliases]):
            return canon
    if any(k == ex or ex in k for ex in EXCLUDE_ALIASES):
        return "__exclude__"
    return k

def _preclean(text: str) -> str:
    # unwrap hyphenated line breaks: "cogni-\n tion" -> "cognition"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # drop single page-number lines / obvious footers
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?mi)^(?:©|\(c\)|copyright|doi:|www\.|permissions@|creative\s*commons).*$", "", text)
    # normalize whitespace
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

# Global header pattern (NOT line-anchored), allows numbering and punctuation:
# Examples matched: "1. Introduction", "Introduction:", "MATERIALS & METHODS", "2) Results"
HEADER_GLOBAL_RE = re.compile(
    r"""
    (?P<label>
        (?:^|\n|(?:\s))                # start or after whitespace/newline
        (?:\d{1,2}\s*[\.\)\-:]\s*)?    # optional numbering like "1." or "2)"
        (?:[A-Z][A-Za-z/&\- ]{2,80}|[A-Z][A-Z/&\- ]{2,80})  # Title Case or ALL CAPS
        \s*(?:section|chapter)?\s*     # optional trailing word
        :?                             # optional colon
    )
    """,
    flags=re.VERBOSE | re.IGNORECASE
)

def split_into_sections(text: str) -> dict:
    text = _preclean(text)
    matches = list(HEADER_GLOBAL_RE.finditer(text))
    if not matches:
        return {"full": text}

    # Build spans with canonical names; filter excluded
    spans = []
    for m in matches:
        raw = m.group("label").strip()
        # strip leading newlines/whitespace and numbering
        raw_clean = re.sub(r"^\s*(\d{1,2}\s*[\.\)\-:]\s*)?", "", raw)
        name = _canon(raw_clean)
        if name == "__exclude__":
            continue
        spans.append((m.start(), name))

    if not spans:
        return {"full": text}

    # Sort spans and carve text chunks
    spans.sort(key=lambda x: x[0])
    sections = {}
    for i, (start, name) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else len(text)
        chunk = text[start:end].strip()
        # keep first occurrence per canonical name
        sections.setdefault(name, chunk)

    # If none of the canonical keys were found, fallback
    if not any(k in sections for k in ORDER):
        return {"full": text}
    return sections

def stitch_sections(sections: dict, max_sections: int = 6) -> str:
    out = []
    for k in ORDER:
        if k in sections:
            out.append(sections[k])
        if len(out) >= max_sections:
            break
    return "\n\n".join(out)
