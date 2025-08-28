import re

def split_into_sections(text: str) -> dict:
    pattern = re.compile(r"\n([A-Z][A-Za-z ]{2,60})\n")
    spans = [(m.start(), m.group(1).strip().lower()) for m in pattern.finditer(text)]
    spans.sort()
    sections = {}
    if not spans:
        return {"full": text}
    for i, (start, name) in enumerate(spans):
        end = spans[i+1][0] if i+1 < len(spans) else len(text)
        sections[name] = text[start:end].strip()
    return sections

def stitch_sections(sections: dict, max_sections: int = 5) -> str:
    order = ["abstract","introduction","methods","results","discussion","conclusion","full"]
    out = []
    for k in order:
        if k in sections:
            out.append(sections[k])
        if len(out) >= max_sections:
            break
    return "\n\n".join(out)