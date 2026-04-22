"""Load and record which articles were already sent: PostgreSQL via DATABASE_URL (e.g. Neon)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import psycopg

from .cfg import RECIPIENT_EMAIL

logger = logging.getLogger(__name__)


def partition_key() -> str:
    """Value stored in `user_key` column: `RECIPIENT_EMAIL` from `config.py` (one row-set per recipient)."""
    return (RECIPIENT_EMAIL or "").strip()


def _require_partition_key() -> str:
    k = partition_key()
    if not k:
        raise RuntimeError("RECIPIENT_EMAIL must be set in config.py to use PostgreSQL for sent history.")
    return k


def _require_dsn() -> str:
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it to your Neon PostgreSQL connection string (see README)."
        )
    return dsn


def load_sent_ids() -> set[str]:
    dsn = _require_dsn()
    key = _require_partition_key()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT article_id FROM sent_article WHERE user_key = %s",
                (key,),
            )
            return {str(r[0]) for r in cur.fetchall()}


def append_sent(articles: list[dict[str, str]]) -> None:
    if not articles:
        return

    dsn = _require_dsn()
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
