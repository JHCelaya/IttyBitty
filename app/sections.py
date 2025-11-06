import re

# Canonical section names and their aliases
SECTION_ALIASES = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background"],
    "methods": [
        "methods", "materials and methods", "materials & methods",
        "material and methods", "method", "participants", "procedure", 
        "procedures", "experimental procedures", "participants and methods",
        "experimental design", "methodology"
    ],
    "results": ["results", "findings", "results and discussion"],
    "discussion": ["discussion", "general discussion"],
    "conclusion": ["conclusion", "conclusions", "concluding remarks"],
}

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