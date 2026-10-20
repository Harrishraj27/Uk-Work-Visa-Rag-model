from __future__ import annotations
import datetime as dt, json, pathlib
from typing import Optional


def parse_ts(s) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def age_days(ts, now: Optional[dt.datetime] = None) -> Optional[float]:
    t = parse_ts(ts)
    if t is None:
        return None
    return ((now or now_utc()) - t).total_seconds() / 86400


def chunk_is_stale(chunk: dict, stale_days: int, now: Optional[dt.datetime] = None) -> bool:
    """Unknown fetch time counts as stale: we cannot show it is current."""
    a = age_days(chunk.get("fetched_at"), now)
    return a is None or a > stale_days


def load_json(path) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def corpus_summary(manifest: dict, check_log: dict) -> dict:
    rows = []
    for sid, m in (manifest.get("sources") or {}).items():
        c = check_log.get(sid, {})
        rows.append({"source_id": sid, "title": m.get("title"), "url": m.get("url"),
                     "page_updated_on": m.get("page_updated_on"), "fetched_at": m.get("fetched_at"),
                     "content_hash": (m.get("content_hash") or "")[:12],
                     "last_success_at": c.get("last_success_at"), "last_result": c.get("last_result", "never checked")})
    fetched = sorted(r["fetched_at"] for r in rows if r["fetched_at"])
    return {"sources": rows, "oldest_fetch": fetched[0] if fetched else None,
            "newest_fetch": fetched[-1] if fetched else None}
