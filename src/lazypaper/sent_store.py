"""Load and record which articles were already sent in the repository-local SQLite store."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parent.parent.parent
_STORE_PATH = _ROOT / "sent_emails.db"
_LEGACY_JSON_PATH = _ROOT / "sent_articles.json"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sent_emails (
    article_id TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    journal TEXT NOT NULL DEFAULT ''
)
"""


def _connect() -> sqlite3.Connection:
    needs_migration = not _STORE_PATH.exists() and _LEGACY_JSON_PATH.exists()
    conn = sqlite3.connect(_STORE_PATH)
    conn.execute(_SCHEMA)
    if needs_migration:
        _migrate_legacy_json(conn)
    return conn


def _migrate_legacy_json(conn: sqlite3.Connection) -> None:
    import json

    try:
        data = json.loads(_LEGACY_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {_LEGACY_JSON_PATH}") from exc

    if not isinstance(data, list):
        raise RuntimeError(f"Expected {_LEGACY_JSON_PATH} to contain a JSON list")

    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        article_id = str(item.get("id", "")).strip()
        if not article_id:
            continue
        rows.append(
            (
                article_id,
                str(item.get("sent_at", "")).strip() or datetime.now(timezone.utc).date().isoformat(),
                str(item.get("title", "")),
                str(item.get("journal", "")),
            )
        )

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO sent_emails (article_id, sent_at, title, journal) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        logger.info("Migrated %s legacy sent article(s) from %s", len(rows), _LEGACY_JSON_PATH.name)


def load_sent_ids() -> set[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT article_id FROM sent_emails").fetchall()
    return {str(row[0]) for row in rows}


def append_sent(articles: list[dict[str, str]]) -> None:
    if not articles:
        return

    today = datetime.now(timezone.utc).date()
    rows = []
    for article in articles:
        article_id = str(article.get("id", "")).strip()
        if not article_id:
            continue
        rows.append(
            (
                article_id,
                today.isoformat(),
                str(article.get("title", "")),
                str(article.get("journal", "")),
            )
        )

    if not rows:
        return

    with _connect() as conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO sent_emails (article_id, sent_at, title, journal) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        logger.info("Recorded %s send(s) in %s", cur.rowcount, _STORE_PATH.name)
