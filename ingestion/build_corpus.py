"""Build data/chunks.jsonl from the latest OK snapshot of each source (manual-review step first!).

Usage: python -m ingestion.build_corpus
Review snapshots/diffs before running. This command never fetches.
"""
from __future__ import annotations
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP, OUT = ROOT / "data" / "snapshots", ROOT / "data" / "chunks.jsonl"
MANIFEST = ROOT / "data" / "manifest.json"
FEW_CHUNKS = 2


def read_snapshot(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"Could not decode snapshot {path}")


def latest_ok(source_dir: pathlib.Path) -> dict | None:
    latest = None
    for f in sorted(source_dir.glob("*.json")):
        snap = read_snapshot(f)
        if snap.get("status") == "ok":
            latest = snap
    return latest


def main() -> None:
    rows = []
    counts = {}
    manifest_sources = {}
    for d in sorted(p for p in SNAP.iterdir() if p.is_dir()):
        latest = latest_ok(d)
        if not latest:
            print(f"FLAG {d.name}: no ok snapshot")
            continue
        chunks = latest.get("chunks") or []
        counts[latest["source_id"]] = len(chunks)
        if len(chunks) == 0:
            print(f"FLAG {latest['source_id']}: zero chunks")
        elif len(chunks) < FEW_CHUNKS:
            print(f"FLAG {latest['source_id']}: only {len(chunks)} chunk(s) (suspiciously few)")
        manifest_sources[latest["source_id"]] = {
            "url": latest["url"],
            "title": latest.get("title"),
            "page_updated_on": latest.get("page_updated_on"),
            "fetched_at": latest.get("fetched_at"),
            "content_hash": latest.get("content_hash"),
            "chunk_count": len(chunks),
        }
        for c in chunks:
            rows.append({
                **c,
                "source_id": latest["source_id"],
                "url": latest["url"],
                "title": latest["title"],
                "page_updated_on": latest["page_updated_on"],
                "fetched_at": latest["fetched_at"],
                "content_hash": latest["content_hash"],
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    MANIFEST.write_text(json.dumps({"sources": manifest_sources, "chunk_count": len(rows)}, indent=2), encoding="utf-8")
    print("Chunks per source:")
    for sid, n in counts.items():
        print(f"  {sid}: {n}")
    print(f"Wrote {len(rows)} chunks to {OUT}")


if __name__ == "__main__":
    main()
