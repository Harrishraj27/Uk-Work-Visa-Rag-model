"""Check allowlisted pages and report which changed. Stages, never activates.

Usage: python -m ingestion.refresh
Outputs a report: changed / unchanged / unverified (fetch failed). A failed check is NOT 'unchanged'.
"""
from __future__ import annotations
import json
from .fetch import SOURCES, SNAP, fetch_one


def latest_hash(source_id: str):
    h = None
    for f in sorted((SNAP / source_id).glob("*.json")):
        s = json.loads(f.read_bytes().decode("utf-8", errors="replace"))
        if s.get("status") == "ok":
            h = s["content_hash"]
    return h


def main() -> None:
    for s in json.loads(SOURCES.read_text())["sources"]:
        if not (s["url"] and s.get("verified")):
            continue
        res = fetch_one(s)
        if res["status"] != "ok":
            print(f"{s['id']}: UNVERIFIED ({res.get('error')})")
            continue
        old = latest_hash(s["id"])
        verdict = "UNCHANGED" if old == res["content_hash"] else ("NEW" if old is None else "CHANGED - review before activating")
        d = SNAP / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        stamp = res["fetched_at"].replace(":", "").replace("-", "")
        (d / f"{stamp}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
        print(f"{s['id']}: {verdict}")


if __name__ == "__main__":
    main()
