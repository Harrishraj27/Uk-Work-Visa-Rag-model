"""System and user prompt templates for evidence-only answers with citations."""

SYSTEM_PROMPT = """\
You are a UK Work Visa Evidence Assistant — a portfolio prototype, NOT legal advice and NOT a UK government service.

Rules:
1. Answer ONLY from the evidence passages provided below. Never invent, assume, or add information beyond them.
2. Every factual sentence MUST end with a citation like [graduate-overview#3]. A citation means "this claim comes from that chunk."
3. If the evidence is insufficient, say exactly: "INSUFFICIENT_EVIDENCE" — never guess.
4. Never make a personal eligibility decision, predict visa success, or calculate whether a specific salary qualifies.
5. If the question asks for personal advice, say the user should check the official GOV.UK guidance or speak to a regulated immigration adviser.
6. Keep the answer short (3-5 sentences). Be factual and neutral.
7. If any passage is marked STALE, warn the user that the information may be outdated and give the fetch date.
"""

USER_TEMPLATE = """\
Question: {question}

Evidence passages (use ONLY these):
{evidence_block}

Answer the question using the passages above. Cite every claim. If the passages do not contain the answer, respond with INSUFFICIENT_EVIDENCE.
"""


def sanitize_evidence_text(text: str) -> str:
    """Sanitize chunk text to prevent breaking out of <evidence> XML boundary."""
    return text.replace("</evidence>", "&lt;/evidence&gt;").replace("<evidence", "&lt;evidence")


def format_evidence_block(chunks: list[dict], stale_ids: set[str] | None = None) -> str:
    """Format retrieved chunks into the XML-like evidence block the prompt expects."""
    stale_ids = stale_ids or set()
    parts = []
    for c in chunks:
        stale_attr = ' stale="true"' if c["id"] in stale_ids else ""
        text = sanitize_evidence_text(c["text"])
        parts.append(
            f'<evidence id="{c["id"]}" source="{c.get("url", "")}" '
            f'fetched="{c.get("fetched_at", "unknown")}"{stale_attr}>\n'
            f'{text}\n'
            f'</evidence>'
        )
    return "\n\n".join(parts)


def build_user_prompt(question: str, chunks: list[dict], stale_ids: set[str] | None = None) -> str:
    return USER_TEMPLATE.format(
        question=question,
        evidence_block=format_evidence_block(chunks, stale_ids),
    )
