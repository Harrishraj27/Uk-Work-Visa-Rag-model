"""Scope and safety guard applied BEFORE any model call, for every provider (real or offline).
Generic pattern classes only: no question-specific answers. A guard hit returns a fixed refusal and never cites
evidence, so a refusal can never be mistaken for a sourced claim."""
from __future__ import annotations
import re
from typing import Optional

SNAPSHOT_YEAR = "2026"

_RULES: list[tuple[str, re.Pattern, str]] = [
    ("secret_request",
     re.compile(r"(reveal|show|print|extract|leak|dump|tell me|give me|output|repeat)\b.{0,60}\b(system (prompt|instruction)s?|api[ -]?keys?|secrets?|environment|env(ironment)? variables?|\.env|passwords?|tokens?|credentials)", re.I | re.S),
     "I can't share system instructions, configuration or any keys or secrets. I only show passages from the stored GOV.UK sources."),
    ("prompt_injection",
     re.compile(r"(ignore|disregard|forget|override|bypass)\b.{0,40}\b(instructions?|rules|guidelines|guidance|policy|prompt)|\b(debug|developer|admin|god) mode\b|^\s*(system|assistant)\s*(instruction|message|prompt)?\s*:|you are now\b|policy (was )?updated today|\bnew rules?:", re.I | re.S),
     "I can't change my rules or accept instructions that claim new policy. I only show what the stored GOV.UK sources say."),
    ("legal_persona",
     re.compile(r"\bact as\b.{0,40}\b(lawyer|solicitor|adviser|advisor|consultant|caseworker|immigration)|\b(evaluate|assess|rate|predict)\b.{0,30}\b(my|me)\b.{0,30}\b(chances?|case|application|eligibility|odds)", re.I | re.S),
     "I can't act as an immigration adviser or assess personal chances. This is a general evidence demo. Check GOV.UK or ask a regulated adviser."),
    ("personal_decision",
     re.compile(r"\b(do|will|would|can|could|am|should)\s+i\b.{0,60}\b(qualify|be eligible|be approved|get approved|be granted|definitely|guaranteed?|for sure)\b|\bguarantee(d|s)?\b.{0,40}\b(me|my|i)\b|\b(am|will) i\b.{0,25}\bguarantee|\bmy (salary|income|offer|job|occupation|code|case|application|employer)\b.{0,60}\b(qualif|enough|meet|eligible|approved|definitely)|\bam i (eligible|guaranteed|allowed)\b|\bdefinitely\b.{0,40}\b(sponsor|approve|get)|\bmy salary is\b|\bwill (my )?(employer|company)\b.{0,30}\bsponsor me\b", re.I | re.S),
     "I can't decide personal eligibility or promise an outcome. Visa decisions are made by the Home Office on the full facts. Check GOV.UK or ask a regulated adviser."),
    ("other_route",
     re.compile(r"\b(innovator|founder|global talent|scale[- ]?up|youth mobility|family visa|spouse visa|high potential|hpi|asylum|ukraine|ancestry|domestic worker|seasonal worker)\b", re.I),
     "That route isn't in the stored sources. This demo only covers the Graduate visa and the Skilled Worker route (including switching and sponsor licences). Check GOV.UK."),
]

_YEAR = re.compile(r"\b(20[0-9]{2})\b")


def check_question(question: str, snapshot_date: str = "") -> Optional[dict]:
    """Return {"rule": ..., "answer": ...} when the question must not go to the model, else None."""
    q = question or ""
    for name, pat, msg in _RULES:
        if pat.search(q):
            # An explicit mention of the two covered routes beats the other_route keyword list only for
            # route names that appear inside a covered-route sentence; keep it strict and simple.
            return {"rule": name, "answer": msg}
    years = {y for y in _YEAR.findall(q) if y != SNAPSHOT_YEAR}
    if years:
        when = f" (fetched {snapshot_date})" if snapshot_date else ""
        return {"rule": "other_year",
                "answer": f"The stored sources are a snapshot{when}. I can't answer for other years ({', '.join(sorted(years))}) or predict future changes. Check GOV.UK or the Home Office archive."}
    return None
