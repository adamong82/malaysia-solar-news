"""SQLite storage: articles, runs, snapshot import/export, dedupe."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash     TEXT UNIQUE NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT DEFAULT '',
    source       TEXT DEFAULT '',
    published_at TEXT,
    collected_at TEXT NOT NULL,
    summary      TEXT DEFAULT '',
    keywords     TEXT DEFAULT '',
    score        REAL DEFAULT 0,
    read         INTEGER DEFAULT 0,
    notified     INTEGER DEFAULT 0,
    topic        TEXT NOT NULL DEFAULT 'solar'
);
CREATE INDEX IF NOT EXISTS idx_articles_published
    ON articles (COALESCE(published_at, collected_at) DESC);
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    seen         INTEGER DEFAULT 0,
    new_count    INTEGER DEFAULT 0,
    notified     INTEGER DEFAULT 0,
    error        TEXT,
    topic        TEXT NOT NULL DEFAULT 'solar'
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Old databases were created before multi-topic support — add the
    topic column where missing (existing rows default to 'solar')."""
    for table in ("articles", "runs"):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if "topic" not in cols:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN topic TEXT"
                f" NOT NULL DEFAULT '{config.DEFAULT_TOPIC}'"
            )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
        _local.conn = conn
    return conn


def url_hash(url: str, title: str = "", source: str = "") -> str:
    """Stable dedupe key: normalized URL, else title+source fallback."""
    u = (url or "").strip().split("#")[0].lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?&](utm_[a-z]+|fbclid|gclid)=[^&]*", "", u)
    if u.startswith(("http://", "https://")):
        u = u.rstrip("/")
    if not u or u in ("http:", "https:"):
        base = f"{title.strip().lower()}|{source.strip().lower()}"
        return "t:" + hashlib.sha256(base.encode()).hexdigest()
    return hashlib.sha256(u.encode()).hexdigest()


def insert_article(conn: sqlite3.Connection, art: dict[str, Any],
                   topic: str = "") -> bool:
    """Insert one article of one topic; returns True if it is new. Dedupes
    on URL hash and on exact (title, source) so the same story surfaced by
    several Google News queries is only stored once (dedupe is global:
    a URL belongs to whichever topic found it first)."""
    if not topic:
        topic = art.get("topic", "")
    if topic not in config.TOPICS:
        topic = config.DEFAULT_TOPIC
    art["topic"] = topic
    h = url_hash(art.get("url", ""), art.get("title", ""), art.get("source", ""))
    exists = conn.execute(
        "SELECT 1 FROM articles WHERE url_hash = ? "
        "OR (lower(trim(title)) = lower(trim(?)) "
        "    AND ifnull(source,'') = ifnull(?,''))",
        (h, art.get("title", ""), art.get("source", "")),
    ).fetchone()
    if exists:
        return False
    conn.execute(
        "INSERT INTO articles (url_hash, title, url, source, published_at,"
        " collected_at, summary, keywords, score, read, notified, topic)"
        " VALUES (?,?,?,?,?,?,?,?,?,0,0,?)",
        (
            h,
            art.get("title", "").strip(),
            art.get("url", ""),
            art.get("source", ""),
            art.get("published_at"),
            art.get("collected_at") or now_iso(),
            art.get("summary", ""),
            art.get("keywords", ""),
            float(art.get("score", 0)),
            topic,
        ),
    )
    return True


def export_snapshot(path: Optional[Path] = None) -> Path:
    """Write a JSON snapshot of all articles (used by GitHub Actions to
    persist state across cloud runs and by GitHub Pages as data file)."""
    path = Path(path or config.SNAPSHOT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    rows = conn.execute(
        "SELECT title, url, source, published_at, collected_at, summary,"
        " keywords, score, read, notified, topic FROM articles"
        " ORDER BY COALESCE(published_at, collected_at) DESC"
    ).fetchall()
    payload = {"generated_at": now_iso(), "articles": [dict(r) for r in rows]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def import_snapshot(path: Optional[Path] = None) -> int:
    """Merge a JSON snapshot back into the DB (no-op for known rows).
    Returns number of newly restored rows."""
    path = Path(path or config.SNAPSHOT_PATH)
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    items = payload.get("articles", []) if isinstance(payload, dict) else payload
    conn = get_conn()
    created = 0
    for item in items:
        if isinstance(item, dict) and item.get("title"):
            if insert_article(conn, item):
                created += 1
    conn.commit()
    return created


def list_articles(
    search: str = "",
    source: str = "",
    unread_only: bool = False,
    topic: str = "",
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conn = get_conn()
    where, params = [], []
    if topic:
        where.append("topic = ?")
        params.append(topic)
    if search:
        where.append("(lower(title) LIKE ? OR lower(summary) LIKE ?)")
        like = f"%{search.lower()}%"
        params += [like, like]
    if source:
        where.append("source = ?")
        params.append(source)
    if unread_only:
        where.append("read = 0")
    sql = (
        "SELECT id, title, url, source, published_at, collected_at, summary,"
        " keywords, score, read, notified FROM articles"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(published_at, collected_at) DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def mark_read(ids: Optional[list[int]] = None, topic: str = "") -> int:
    conn = get_conn()
    if ids is None:
        if topic:
            cur = conn.execute(
                "UPDATE articles SET read = 1 WHERE read = 0 AND topic = ?",
                (topic,),
            )
        else:
            cur = conn.execute("UPDATE articles SET read = 1 WHERE read = 0")
    else:
        if not ids:
            return 0
        marks = ",".join("?" for _ in ids)
        cur = conn.execute(f"UPDATE articles SET read = 1 WHERE id IN ({marks})", ids)
    conn.commit()
    return cur.rowcount


def stats(topic: str = "") -> dict[str, Any]:
    """Dashboard stats; topic='' means all topics combined."""
    conn = get_conn()
    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
    tw = " WHERE topic = ?" if topic else ""
    tp = (topic,) if topic else ()
    one = lambda sql, p=(): conn.execute(sql, p).fetchone()[0]  # noqa: E731
    sources = [
        dict(r)
        for r in conn.execute(
            "SELECT source, COUNT(*) AS n FROM articles"
            " WHERE source != ''" + (" AND topic = ?" if topic else "")
            + " GROUP BY source ORDER BY n DESC LIMIT 20",
            tp,
        ).fetchall()
    ]
    run_where = " WHERE topic = ?" if topic else ""
    last_run = conn.execute(
        f"SELECT * FROM runs{run_where} ORDER BY id DESC LIMIT 1", tp
    ).fetchone()
    return {
        "total": one(f"SELECT COUNT(*) FROM articles{tw}", tp),
        "unread": one(f"SELECT COUNT(*) FROM articles{tw}" + (" AND read = 0" if topic else " WHERE read = 0"), tp),
        "last_24h": one(
            f"SELECT COUNT(*) FROM articles{tw}" + (" AND" if topic else " WHERE")
            + " COALESCE(published_at, collected_at) >= ?",
            tp + (day_ago,),
        ),
        "sources": sources,
        "last_run": dict(last_run) if last_run else None,
        "topic": topic,
        "scheduler_enabled": config.ENABLE_SCHEDULER,
        "interval_min": config.COLLECT_INTERVAL_MIN,
        "telegram_configured": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID),
    }


def record_run(started_at: str, seen: int, new_count: int, notified: int,
               error: str = "", topic: str = "") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO runs (started_at, finished_at, seen, new_count, notified, error, topic)"
        " VALUES (?,?,?,?,?,?,?)",
        (started_at, now_iso(), seen, new_count, notified, error,
         topic or config.DEFAULT_TOPIC),
    )
    conn.commit()
