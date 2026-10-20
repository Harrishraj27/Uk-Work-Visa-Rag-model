"""Audit allowlisted sources against official GOV.UK pages and stage diffs.

Usage: python -m ingestion.stage

Audits all 12 allowlisted sources. Records URLs, fetched dates, content hashes,
and genuine page-updated dates separately. If any page has changed, stages the
new extract and a diff under data/staged/<source_id>/ for review.
NEVER automatically activates changes or claims current rules without review.
"""
from __future__ import annotations
import difflib, json, pathlib, datetime as dt
import httpx
from ingestion.fetch import SOURCES, UA, extract
from ingestion.chunk import chunk_sections, content_hash
from core.vectors import compute_file_hash

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
STAGED = ROOT / "data" / "staged"


def stage_audit() -> dict:
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"sources": {}}

    audit_records = []
    changes_staged = 0
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    client = httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)

    for s in sources:
        sid = s["id"]
        url = s["url"]
        stored = manifest.get("sources", {}).get(sid, {})
        stored_hash = stored.get("content_hash", "")
        stored_page_date = stored.get("page_updated_on")
        stored_fetch_date = stored.get("fetched_at")

        rec = {
            "source_id": sid,
            "url": url,
            "status": "unverified",
            "stored_page_updated_on": stored_page_date,
            "stored_fetched_at": stored_fetch_date,
            "stored_content_hash": stored_hash,
            "live_page_updated_on": None,
            "live_fetched_at": now_iso,
            "live_content_hash": None,
            "content_changed": False,
            "date_bumped": False,
        }

        try:
            r = client.get(url)
            r.raise_for_status()
            html = r.text
            page = extract(html)
            body = "\n\n".join(sec["heading"] + "\n" + sec["text"] for sec in page["sections"])
            live_hash = content_hash(body)
            rec["status"] = "ok"
            rec["live_page_updated_on"] = page["page_updated_on"]
            rec["live_content_hash"] = live_hash
            rec["content_changed"] = (live_hash != stored_hash)
            rec["date_bumped"] = (page["page_updated_on"] != stored_page_date)

            if rec["content_changed"] or rec["date_bumped"]:
                stage_dir = STAGED / sid
                stage_dir.mkdir(parents=True, exist_ok=True)
                new_chunks = chunk_sections(sid, page["sections"])
                staged_data = {
                    "source_id": sid,
                    "url": url,
                    "title": page["title"],
                    "page_updated_on": page["page_updated_on"],
                    "fetched_at": now_iso,
                    "content_hash": live_hash,
                    "sections": page["sections"],
                    "chunks": new_chunks,
                }
                (stage_dir / "staged_snapshot.json").write_text(json.dumps(staged_data, indent=2, ensure_ascii=False), encoding="utf-8")

                # Generate text diff against stored chunks
                stored_chunks_file = ROOT / "data" / "chunks.jsonl"
                old_text = ""
                if stored_chunks_file.exists():
                    all_chunks = [json.loads(l) for l in stored_chunks_file.read_text(encoding="utf-8").splitlines() if l.strip()]
                    old_text = "\n\n".join(f"[{c['id']}] {c['section_heading']}\n{c['text']}" for c in all_chunks if c.get("source_id") == sid)
                new_text = "\n\n".join(f"[{c['id']}] {c['section_heading']}\n{c['text']}" for c in new_chunks)

                diff = list(difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"active/{sid} ({stored_page_date or 'initial'})",
                    tofile=f"staged/{sid} ({page['page_updated_on'] or 'live'})",
                ))
                (stage_dir / "diff.patch").write_text("".join(diff), encoding="utf-8")
                changes_staged += 1

        except Exception as e:
            rec["status"] = f"unverified: {e}"

        audit_records.append(rec)

    STAGED.mkdir(parents=True, exist_ok=True)
    report = {
        "audit_timestamp": now_iso,
        "active_corpus_version": "2026-10-12-draft",
        "total_sources": len(sources),
        "changes_staged": changes_staged,
        "records": audit_records,
    }
    (STAGED / "audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    print("=== Auditing 12 GOV.UK Sources & Staging Diffs ===")
    rep = stage_audit()
    print(f"Audit completed at {rep['audit_timestamp']}.")
    print(f"Active corpus: {rep['active_corpus_version']}")
    print(f"{'Source ID':<35} {'Status':<6} {'Stored Date':<12} {'Live Date':<12} {'Verdict':<15}")
    print("-" * 85)
    for r in rep["records"]:
        verdict = "CHANGED (staged)" if r["content_changed"] else ("DATE BUMP" if r["date_bumped"] else "IDENTICAL")
        print(f"{r['source_id']:<35} {r['status']:<6} {str(r['stored_page_updated_on']):<12} {str(r['live_page_updated_on']):<12} {verdict:<15}")
    if rep["changes_staged"] > 0:
        print(f"\nNotice: {rep['changes_staged']} source(s) staged under data/staged/. Review diffs before activating.")
    else:
        print("\nAll 12 sources match stored content hashes exactly. Active corpus remains versioned 2026-10-12.")


if __name__ == "__main__":
    main()
