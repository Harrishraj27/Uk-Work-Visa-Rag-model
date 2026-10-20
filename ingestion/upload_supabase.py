"""Load source_versions + chunks (+ vectors) into a Supabase DEV project via PostgREST.
Needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your local .env (backend only; never put it in the web app,
Docker image or chat). Re-running is safe: rows are upserted by natural keys.

Usage: python -m ingestion.upload_supabase [--dry-run]
"""
from __future__ import annotations
import argparse, json, pathlib
import httpx
from core.config import ConfigError, load_settings
from core.vectors import validate_vector_store


def _post(http, base, key, table, rows, on_conflict):
    r = http.post(f"{base}/rest/v1/{table}?on_conflict={on_conflict}",
                  headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                           "Prefer": "resolution=merge-duplicates,return=representation"}, json=rows)
    r.raise_for_status()
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    s = load_settings()
    chunks = [json.loads(l) for l in pathlib.Path(s.chunks_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    meta, vectors = validate_vector_store(s)   # refuses fake/stale/mismatched vectors in real mode
    if meta.get("is_fake") or meta.get("provider") == "fake":
        print("NOTE: these vectors are labelled FAKE (offline). Do not use them for real retrieval.")
    seen = {}
    for c in chunks:
        seen.setdefault(c["source_id"], c)
    print(f"{len(seen)} source versions, {len(chunks)} chunks, {len(vectors)} vectors, dim={s.embedding_dim}")
    if a.dry_run:
        print("Dry run: nothing sent."); return
    if not s.supabase_url or not s.supabase_service_key:
        raise ConfigError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env (dev project).")
    with httpx.Client(timeout=60) as http:
        sv_rows = [{"source_id": sid, "url": c["url"], "title": c["title"], "page_updated_on": c.get("page_updated_on"),
                    "fetched_at": c["fetched_at"], "content_hash": c["content_hash"], "status": "active"} for sid, c in seen.items()]
        got = _post(http, s.supabase_url, s.supabase_service_key, "source_versions", sv_rows, "source_id,content_hash")
        ids = {(r["source_id"], r["content_hash"]): r["id"] for r in got}
        rows = [{"id": c["id"], "source_version_id": ids[(c["source_id"], c["content_hash"])],
                 "section_heading": c["section_heading"], "position": c["position"], "text": c["text"],
                 "embedding": vectors.get(c["id"])} for c in chunks]
        for i in range(0, len(rows), 25):
            _post(http, s.supabase_url, s.supabase_service_key, "chunks", rows[i:i + 25], "id")
    print(f"Uploaded {len(rows)} chunks.")


if __name__ == "__main__":
    main()
