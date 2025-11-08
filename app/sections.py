# app/sections.py
import re
from typing import Dict, List, Tuple

<<<<<<< HEAD
# Canonical buckets in the order we want to stitch/summarize
ORDER = ["abstract","introduction","methods","results","discussion","conclusion","full"]

# Common aliases you see in journals
ALIASES = {
    "abstract": ["abstract", "summary", "synopsis"],
    "introduction": ["introduction", "background", "overview", "aims"],
    "methods": [
        "methods", "materials and methods", "materials & methods",
        "method", "participants", "subjects", "procedures", "experimental procedures",
=======
# Canonical section names and their aliases
SECTION_ALIASES = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background"],
    "methods": [
        "methods", "materials and methods", "materials & methods",
        "material and methods", "method", "participants", "procedure", 
        "procedures", "experimental procedures", "participants and methods",
        "experimental design", "methodology"
>>>>>>> 48d9b895cab7a942dd21f6618bd5c09906fdfb60
    ],
    "results": ["results", "findings", "outcomes"],
    "discussion": ["discussion", "general discussion"],
    "conclusion": ["conclusion", "conclusions", "concluding remarks"],
}

<<<<<<< HEAD
# Build a fast alias lookup
_ALIAS_TO_CANON = {}
for canon, alist in ALIASES.items():
    for a in alist + [canon]:
        _ALIAS_TO_CANON[a.lower()] = canon

# Heuristic header patterns:
#  - lines in ALL CAPS or Title Case
#  - allow punctuation and digits for numbered headings ("2. Methods", "2 Methods")
_HEADER_LINE = re.compile(
    r"^\s*(?P<h>(?:[A-Z][A-Za-z0-9 \-:/&]{2,80}|[A-Z0-9 ][A-Z0-9 \-:/&]{2,80}))\s*$",
    re.MULTILINE,
)

# When journals print running headers/footers; also fix hyphenation at line breaks
_WS = r"[ \t]"
_PAGE_NO = re.compile(rf"^\s*(?:\d+|Page\s+\d+)\s*$", re.MULTILINE)
_RUNNING_HDR = re.compile(rf"^\s*(?:bioRxiv|medRxiv|arXiv|Elsevier|Springer|Wiley|Nature|PNAS).*$", re.MULTILINE)
# de-hyphenate words broken at line end: "hippo-\ncampus" -> "hippocampus"
_DEHYPH = re.compile(r"-\n(?=[a-z])")
# collapse excessive newlines
_COLLAPSE = re.compile(r"\n{3,}")

def _normalize(text: str) -> str:
    t = text.replace("\r\n", "\n")
    t = _DEHYPH.sub("", t)
    # remove lone page numbers / running headers
    t = _PAGE_NO.sub("", t)
    t = _RUNNING_HDR.sub("", t)
    t = _COLLAPSE.sub("\n\n", t)
    return t

def _normalize_header(h: str) -> str:
    key = h.strip().rstrip(":").lower()
    key = re.sub(r"\b&\b", "and", key)
    key = re.sub(r"^\d+[\.\)]\s*", "", key)   # drop leading “2. ” or “2) ”
    # exact or alias
    if key in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[key]
    # fuzzy startswith/contains
    for canon, alist in ALIASES.items():
        if key.startswith(canon) or any(key.startswith(a) or a in key for a in alist):
            return canon
    return key  # unknown -> keep as-is

def _split_by_headers(text: str) -> Dict[str, str]:
    matches = list(_HEADER_LINE.finditer(text))
    if not matches:
        return {}
    spans: List[Tuple[int, str]] = []
    for m in matches:
        name = _normalize_header(m.group("h"))
        spans.append((m.start(), name))
    spans.sort(key=lambda x: x[0])

    sections: Dict[str, str] = {}
    for i, (start, name) in enumerate(spans):
        end = spans[i+1][0] if i+1 < len(spans) else len(text)
        chunk = text[start:end].strip()
        if not chunk:
            continue
        # keep only the first occurrence per canonical section
        if name not in sections:
            sections[name] = chunk
    return sections

# Keyword anchors as a fallback when headers aren’t formatted clearly
_ANCHORS = [
    ("abstract", r"\babstract\b"),
    ("introduction", r"\bintroduction\b|\bbackground\b"),
    ("methods", r"\bmethods?\b|\bmaterials\s*(?:&|and)\s*methods\b|\bparticipants\b|\bprocedures?\b"),
    ("results", r"\bresults?\b|\bfindings?\b|\boutcomes?\b"),
    ("discussion", r"\bdiscussion\b"),
    ("conclusion", r"\bconclusion[s]?\b|\bconcluding\b"),
]

def _split_by_anchors(text: str) -> Dict[str, str]:
    low = text.lower()
    hits: List[Tuple[int,str]] = []
    for canon, pat in _ANCHORS:
        m = re.search(pat, low, flags=re.I)
        if m:
            hits.append((m.start(), canon))
    if not hits:
        return {}
    hits.sort()
    sections: Dict[str, str] = {}
    for i, (start, canon) in enumerate(hits):
        end = hits[i+1][0] if i+1 < len(hits) else len(text)
        chunk = text[start:end].strip()
        if chunk and canon not in sections:
            sections[canon] = chunk
    return sections

def split_into_sections(text: str, mode: str = "hybrid") -> Dict[str, str]:
    """
    Return dict of {section_name: text}. Always returns something; if nothing matches, {'full': text}.
    mode: 'headers' | 'anchors' | 'hybrid'
    """
    if not text or not text.strip():
        return {"full": text or ""}

    norm = _normalize(text)

    if mode == "headers":
        sec = _split_by_headers(norm)
    elif mode == "anchors":
        sec = _split_by_anchors(norm)
    else:  # hybrid: headers first, then fill missing via anchors
        sec = _split_by_headers(norm)
        if not sec:
            sec = _split_by_anchors(norm)
        else:
            anchor_sec = _split_by_anchors(norm)
            for k, v in anchor_sec.items():
                sec.setdefault(k, v)

    # ensure at least a full
    if not any(k in sec for k in ORDER[:-1]):
        return {"full": norm}
    return sec

def stitch_sections(sections: Dict[str, str], max_sections: int = 6) -> str:
    out: List[str] = []
    for k in ORDER:
        if k in sections:
            out.append(sections[k])
        if len(out) >= max_sections:
            break
    return "\n\n".join(out) if out else ""
=======
EXCLUDE_ALIASES = {
    "references", "bibliography", "acknowledgments", "acknowledgements",
    "supplement", "supplementary", "appendix", "author contributions",
    "funding", "conflict of interest", "competing interests", "data availability",
}

ORDER = ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]

def _canon(key: str) -> str:
    """Normalize a header string to canonical name or exclude marker."""
    k = key.strip().lower().strip(":.;,- ")
    
    # Check exclusions first
    if any(ex in k for ex in EXCLUDE_ALIASES):
        return "__exclude__"
    
    # Check canonical mappings
    for canon, aliases in SECTION_ALIASES.items():
        if k in aliases or any(alias in k for alias in aliases):
            return canon
    
    return k

def _preclean(text: str) -> str:
    """Remove common noise from extracted PDF text."""
    # Fix hyphenated line breaks
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Remove page numbers
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Remove copyright/footer lines
    text = re.sub(r"(?mi)^(?:©|\(c\)|copyright|doi:|www\.|creative\s*commons).*$", "", text)
    # Normalize whitespace
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def split_into_sections(text: str) -> dict:
    """
    Split paper text into sections based on headers.
    Returns dict mapping canonical section names to their text content.
    
    This version handles PDFs where sections are embedded in running text
    (not on separate lines).
    """
    text = _preclean(text)
    
    # Build pattern that finds section headers even when embedded in text
    # Look for: "Introduction" followed by uppercase letter or sentence
    # Examples: "IntroductionThe hippocampus", "Introduction The hippocampus"
    
    all_section_words = []
    for aliases in SECTION_ALIASES.values():
        all_section_words.extend(aliases)
    
    # Create pattern for each section type
    patterns = []
    
    # Pattern 1: Section name at start of line (traditional)
    patterns.append(
        re.compile(
            r'^(?:\d+\.?\s*)?(' + '|'.join(re.escape(w) for w in all_section_words) + r')(?:\s|\.|\:|$)',
            re.IGNORECASE | re.MULTILINE
        )
    )
    
    # Pattern 2: Section name embedded in text (for PDFs with no line breaks)
    # Look for section name followed by capital letter (start of sentence)
    patterns.append(
        re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in all_section_words) + r')(?:\.|:)?\s*[A-Z]',
            re.IGNORECASE
        )
    )
    
    all_matches = []
    for pattern in patterns:
        for m in pattern.finditer(text):
            header_text = m.group(1).strip()
            canonical = _canon(header_text)
            
            # Skip excluded sections and unrecognized headers
            if canonical == "__exclude__" or canonical not in SECTION_ALIASES:
                continue
            
            # Store: (position, canonical_name, end_of_match)
            all_matches.append((m.start(), canonical, m.end()))
    
    # Remove duplicates and sort by position
    all_matches = sorted(set(all_matches), key=lambda x: x[0])
    
    # If no sections found, return full text
    if not all_matches:
        return {"full": text}
    
    # Extract text between headers
    sections = {}
    for i, (start, name, header_end) in enumerate(all_matches):
        # Get end position (start of next section or end of text)
        if i + 1 < len(all_matches):
            end = all_matches[i + 1][0]
        else:
            end = len(text)
        
        # Extract content
        content = text[header_end:end].strip()
        
        # For embedded headers, we might catch the first word of the section
        # Clean it up by ensuring we start with a capital letter
        if content and not content[0].isupper():
            # Find first sentence start
            match = re.search(r'[A-Z]', content)
            if match:
                content = content[match.start():]
        
        # Only add if we have substantial content (at least 200 chars)
        if len(content) > 200:
            # Keep first occurrence of each section
            if name not in sections:
                sections[name] = content
    
    # If we found nothing substantial, return full text
    if not sections:
        return {"full": text}
    
    return sections

def stitch_sections(sections: dict, max_sections: int = 6) -> str:
    """
    Combine sections in standard order.
    Returns concatenated text with section markers.
    """
    out = []
    for name in ORDER:
        if name in sections and len(out) < max_sections:
            out.append(f"=== {name.upper()} ===\n{sections[name]}")
    
    # If nothing found in order, just concatenate all
    if not out:
        for name, content in sections.items():
            out.append(f"=== {name.upper()} ===\n{content}")
    
    return "\n\n".join(out)
>>>>>>> 48d9b895cab7a942dd21f6618bd5c09906fdfb60
