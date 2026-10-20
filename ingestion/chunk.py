"""Turn a cleaned page (list of sections) into versioned chunks with stable IDs."""
from __future__ import annotations
import hashlib, re

MAX_CHARS = 1200


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_paragraphs(text: str, limit: int = MAX_CHARS) -> list[str]:
    parts, cur = [], ""
    for para in re.split(r"\n{2,}", text.strip()):
        if cur and len(cur) + len(para) + 2 > limit:
            parts.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        parts.append(cur.strip())
    return parts


def chunk_sections(source_id: str, sections: list[dict]) -> list[dict]:
    """sections: [{'heading': str, 'text': str}] -> chunks with id '<source_id>#<n>'."""
    chunks, n = [], 0
    for sec in sections:
        for piece in _split_paragraphs(sec["text"]):
            n += 1
            chunks.append({"id": f"{source_id}#{n}", "section_heading": sec["heading"],
                           "position": n, "text": piece})
    return chunks
