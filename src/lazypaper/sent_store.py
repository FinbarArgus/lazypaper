"""Load and record which articles were already sent: PostgreSQL (if DATABASE_URL) or sent_articles.json."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .cfg import RECIPIENT_EMAIL

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SENT_FILE = REPO_ROOT / "sent_articles.json"


def partition_key() -> str:
    """Value stored in `user_key` column: `RECIPIENT_EMAIL` from `config.py` (one row-set per recipient)."""
    return (RECIPIENT_EMAIL or "").strip()


def _require_partition_key() -> str:
    k = partition_key()
    if not k:
        raise RuntimeError("RECIPIENT_EMAIL must be set in config.py to use PostgreSQL for sent history.")
    return k


def _using_postgres() -> bool:
    return bool((os.environ.get("DATABASE_URL") or "").strip())


def load_sent_ids() -> set[str]:
    if _using_postgres():
        return _load_sent_ids_postgres()
    return _load_sent_ids_file()


def append_sent(articles: list[dict[str, str]]) -> None:
    if not articles:
        return
    if _using_postgres():
        _append_sent_postgres(articles)
    else:
        _append_sent_file(articles)


def _load_sent_ids_postgres() -> set[str]:
    import psycopg

    dsn = os.environ["DATABASE_URL"].strip()
    key = _require_partition_key()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT article_id FROM sent_article WHERE user_key = %s",
                (key,),
            )
            return {str(r[0]) for r in cur.fetchall()}


def _append_sent_postgres(articles: list[dict[str, str]]) -> None:
    import psycopg

    dsn = os.environ["DATABASE_URL"].strip()
    key = _require_partition_key()
    today = datetime.now(timezone.utc).date()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for a in articles:
                cur.execute(
                    """
                    INSERT INTO sent_article (user_key, article_id, sent_at, title, journal)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_key, article_id) DO NOTHING
                    """,
                    (
                        key,
                        a["id"],
                        today,
                        a.get("title", ""),
                        a.get("journal", ""),
                    ),
                )
        conn.commit()
    logger.info("Recorded %s send(s) in PostgreSQL", len(articles))


def _load_sent_ids_file() -> set[str]:
    if not SENT_FILE.exists():
        return set()
    try:
        data = json.loads(SENT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Could not parse %s; treating as empty", SENT_FILE)
        return set()
    ids: set[str] = set()
    for row in data:
        if isinstance(row, dict) and row.get("id"):
            ids.add(str(row["id"]))
    return ids


def _append_sent_file(articles: list[dict[str, str]]) -> None:
    rows: list[dict] = []
    if SENT_FILE.exists():
        try:
            rows = json.loads(SENT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []
    if not isinstance(rows, list):
        rows = []
    today = datetime.now(timezone.utc).date().isoformat()
    for article in articles:
        rows.append(
            {
                "id": article["id"],
                "sent_at": today,
                "title": article.get("title", ""),
                "journal": article.get("journal", ""),
            }
        )
    SENT_FILE.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    logger.info("Recorded %s send(s) in %s", len(articles), SENT_FILE)
