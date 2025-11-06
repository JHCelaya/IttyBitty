# app/sections.py
import re
from typing import Dict, List, Tuple

# Canonical buckets in the order we want to stitch/summarize
ORDER = ["abstract","introduction","methods","results","discussion","conclusion","full"]

# Common aliases you see in journals
ALIASES = {
    "abstract": ["abstract", "summary", "synopsis"],
    "introduction": ["introduction", "background", "overview", "aims"],
    "methods": [
        "methods", "materials and methods", "materials & methods",
        "method", "participants", "subjects", "procedures", "experimental procedures",
    ],
    "results": ["results", "findings", "outcomes"],
    "discussion": ["discussion", "general discussion"],
    "conclusion": ["conclusion", "conclusions", "concluding remarks", "summary and conclusions"],
}

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
