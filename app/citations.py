"""Citation validation: every cited ID must exist in the retrieved set, and every excerpt shown must be real text.
A working link is not proof of support; claim-level support still needs manual review in eval."""
from __future__ import annotations
import re

CITE_RE = re.compile(r"\[([a-z0-9\-]+#\d+)\]")


def extract_citations(answer: str) -> list[str]:
    return CITE_RE.findall(answer)


def validate_citations(answer: str, retrieved: list[dict]) -> dict:
    valid_ids = {c["id"] for c in retrieved}
    cited = extract_citations(answer)
    invalid = [c for c in cited if c not in valid_ids]
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s]
    uncited = [s for s in sentences if not CITE_RE.search(s)]
    return {"cited": cited, "invalid_ids": invalid, "uncited_sentences": uncited,
            "ok": bool(cited) and not invalid and not uncited}
