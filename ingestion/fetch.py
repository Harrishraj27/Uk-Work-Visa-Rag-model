"""Fetch allowlisted pages locally and save a dated snapshot.

Usage:  python -m ingestion.fetch            # fetch all verified sources
        python -m ingestion.fetch --id graduate-overview

A failed fetch is recorded as status 'unverified', never 'unchanged'.
Run this on your own machine; do not run ingestion inside the web container.
"""
from __future__ import annotations
import argparse, json, pathlib, datetime as dt, re
import httpx
from bs4 import BeautifulSoup, Tag
from .chunk import chunk_sections, content_hash

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshots"
SOURCES = ROOT / "ingestion" / "sources.json"
UA = "uk-work-visa-rag-portfolio/0.1 (educational prototype)"

SKIP_HEADINGS = {
    "contents",
    "related content",
    "explore the topic",
    "collection",
    "share this page",
    "print this page",
    "help improve this page",
    "is this page useful",
}

REMOVE_SELECTORS = [
    "nav", "script", "style", "footer", "form",
    ".gem-c-contents-list", ".govuk-breadcrumbs",
    ".gem-c-related-navigation", ".gem-c-share-links",
    ".govuk-cookie-banner", ".gem-c-feedback",
    ".govuk-phase-banner", ".gem-c-print-link",
    "#contents", ".contents-list",
]


def _page_updated_on(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": "govuk:updated-at"}) or soup.find(
        "meta", attrs={"name": "govuk:first-published-at"}
    )
    if meta and meta.get("content"):
        return meta["content"][:10]
    time_el = soup.find("time", attrs={"datetime": True})
    if time_el and time_el.get("datetime"):
        return time_el["datetime"][:10]
    return None


def _cell_text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def extract(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    updated = _page_updated_on(soup)

    for sel in REMOVE_SELECTORS:
        for tag in soup.select(sel):
            tag.decompose()

    main = soup.select_one(".gem-c-govspeak, .govuk-govspeak") or soup.find("main") or soup
    sections, cur, last = [], {"heading": title or "Introduction", "text": ""}, ""

    def flush():
        if cur["text"].strip() and cur["heading"].lower() not in SKIP_HEADINGS:
            sections.append({"heading": cur["heading"], "text": cur["text"]})

    for el in main.find_all(["h2", "h3", "p", "li", "tr"]):
        if el.find_parent(["h2", "h3", "p", "li", "tr"]):
            continue
        if el.name in ("h2", "h3"):
            heading = el.get_text(" ", strip=True)
            flush()
            cur["heading"], cur["text"], last = heading, "", ""
            continue
        if cur["heading"].lower() in SKIP_HEADINGS:
            continue
        if el.name == "tr":
            cells = [_cell_text(c) for c in el.find_all(["th", "td"])]
            t = " | ".join(c for c in cells if c)
        else:
            t = el.get_text(" ", strip=True)
        if not t or t == last:
            continue
        last = t
        cur["text"] += t + "\n\n"
    flush()
    return {"title": title, "page_updated_on": updated, "sections": sections}


def fetch_one(src: dict) -> dict:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    base = {"source_id": src["id"], "url": src["url"], "fetched_at": now}
    try:
        r = httpx.get(src["url"], headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        r.raise_for_status()
        html = r.content.decode("utf-8")
    except Exception as e:  # noqa: BLE001
        return {**base, "status": "unverified", "error": str(e)}
    page = extract(html)
    body = "\n\n".join(s["heading"] + "\n" + s["text"] for s in page["sections"])
    return {**base, "status": "ok", "title": page["title"], "page_updated_on": page["page_updated_on"],
            "content_hash": content_hash(body), "sections": page["sections"],
            "chunks": chunk_sections(src["id"], page["sections"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    args = ap.parse_args()
    srcs = [s for s in json.loads(SOURCES.read_text(encoding="utf-8"))["sources"] if s["url"] and s.get("verified")]
    if args.id:
        srcs = [s for s in srcs if s["id"] == args.id]
    if not srcs:
        print("No verified sources. Open each URL, confirm it, then set \"verified\": true in ingestion/sources.json.")
        return
    for s in srcs:
        res = fetch_one(s)
        d = SNAP / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        stamp = res["fetched_at"].replace(":", "").replace("-", "")
        (d / f"{stamp}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(s["id"], res["status"], res.get("content_hash", "")[:12], "chunks", len(res.get("chunks") or []))


if __name__ == "__main__":
    main()
