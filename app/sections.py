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
    """Improved section detection for academic papers."""
    text = _preclean(text)
    
    # More comprehensive section patterns
    section_patterns = [
        # Numbered sections: "1. Introduction", "2.1 Methods"
        r'^\s*\d+(?:\.\d+)*\.?\s+(Introduction|Methods?|Results?|Discussion|Conclusion)',
        # Standalone headers
        r'^\s*(ABSTRACT|INTRODUCTION|METHODS?|RESULTS?|DISCUSSION|CONCLUSIONS?)\s*$',
        # With colons
        r'^\s*(Abstract|Introduction|Methods?|Results?|Discussion|Conclusions?):\s*$',
    ]
    
    combined_pattern = '|'.join(f'({p})' for p in section_patterns)
    pattern = re.compile(combined_pattern, re.IGNORECASE | re.MULTILINE)
    
    matches = []
    for match in pattern.finditer(text):
        # Get the actual section name from whichever group matched
        section_name = None
        for group in match.groups():
            if group:
                section_name = group.strip().lower()
                # Normalize variations
                section_name = section_name.replace(':', '').strip()
                if 'method' in section_name:
                    section_name = 'methods'
                elif 'result' in section_name:
                    section_name = 'results'
                elif 'conclusion' in section_name:
                    section_name = 'conclusion'
                break
        
        if section_name:
            matches.append((match.start(), section_name, match.end()))
    
    # If no sections found, return full text
    if not matches:
        return {"full_text": text}
    
    sections = {}
    for i, (start, name, header_end) in enumerate(matches):
        # Get content until next section
        if i + 1 < len(matches):
            end = matches[i + 1][0]
        else:
            end = len(text)
        
        content = text[header_end:end].strip()
        
        # Only keep if substantial (minimum 500 chars for a real section)
        if len(content) > 500:
            sections[name] = content[:10000]  # Cap each section
    
    return sections if sections else {"full_text": text}

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