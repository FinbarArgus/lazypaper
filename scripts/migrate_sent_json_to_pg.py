#!/usr/bin/env python3
"""
One-time import of repo-root sent_articles.json into PostgreSQL.

Requires DATABASE_URL. Rows are stored under user_key = RECIPIENT_EMAIL from config.py.

  pip install -r requirements.txt
  export DATABASE_URL='postgresql://...'
  python scripts/migrate_sent_json_to_pg.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_cfg():
    spec = importlib.util.spec_from_file_location("cfg", ROOT / "config.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load {ROOT / 'config.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser(description="Import sent_articles.json into PostgreSQL")
    parser.add_argument(
        "--json-path",
        type=Path,
        default=ROOT / "sent_articles.json",
        help="Path to sent_articles.json",
    )
    args = parser.parse_args()

    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("ERROR: set DATABASE_URL", file=sys.stderr)
        return 1

    path = args.json_path
    if not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    config = _load_cfg()
    user_key = (getattr(config, "RECIPIENT_EMAIL", None) or "").strip()
    if not user_key:
        print("ERROR: RECIPIENT_EMAIL is empty in config.py", file=sys.stderr)
        return 1
    print(f"Partition (user_key / recipient): {user_key!r}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("ERROR: JSON must be a list of objects", file=sys.stderr)
        return 1

    from datetime import date

    def _sent_date(row: dict) -> date:
        v = row.get("sent_at")
        if not v:
            return date.today()
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return date.today()

    import psycopg

    inserted = 0
    skipped = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for row in raw:
                if not isinstance(row, dict) or not row.get("id"):
                    skipped += 1
                    continue
                aid = str(row["id"])
                sent_d = _sent_date(row)
                title = str(row.get("title", ""))
                journal = str(row.get("journal", ""))
                cur.execute(
                    """
                    INSERT INTO sent_article (user_key, article_id, sent_at, title, journal)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_key, article_id) DO NOTHING
                    """,
                    (user_key, aid, sent_d, title, journal),
                )
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        conn.commit()

    print(f"Done. Inserted (new rows): {inserted}, skipped (duplicate or bad): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
