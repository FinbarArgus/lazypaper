#!/usr/bin/env python3
"""Fetch journal feeds, pick a relevant unsent article, email it, record the send."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .config import INTERESTS
from .emailer import send_article_email, send_no_articles_email
from .fetcher import fetch_all_articles
from .scorer import filter_unsent, pick_article

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Repo root: .../src/lazypaper/main.py -> .../
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SENT_FILE = REPO_ROOT / "sent_articles.json"


def _normalise_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        path = p.path or "/"
        if path.endswith("/") and len(path) > 1:
            path = path.rstrip("/")
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", "", ""))
    except Exception:
        return url.strip()


def _dedupe_articles(articles: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for a in articles:
        nid = _normalise_url(a.get("link", "") or a.get("id", ""))
        if not nid or nid in seen:
            continue
        seen.add(nid)
        b = dict(a)
        b["id"] = nid
        b["link"] = nid
        out.append(b)
    return out


def load_sent_ids() -> set[str]:
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


def append_sent(article: dict[str, str]) -> None:
    rows: list[dict] = []
    if SENT_FILE.exists():
        try:
            rows = json.loads(SENT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []
    if not isinstance(rows, list):
        rows = []
    today = datetime.now(timezone.utc).date().isoformat()
    rows.append(
        {
            "id": article["id"],
            "sent_at": today,
            "title": article.get("title", ""),
            "journal": article.get("journal", ""),
        }
    )
    SENT_FILE.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    logger.info("Fetching feeds…")
    raw = fetch_all_articles()
    articles = _dedupe_articles(raw)
    logger.info("Collected %s unique articles from feeds", len(articles))

    sent = load_sent_ids()
    candidates = filter_unsent(articles, sent)
    logger.info("%s candidates after removing %s already sent", len(candidates), len(sent))

    if not candidates:
        logger.warning("No unsent articles; sending notice email")
        send_no_articles_email()
        return 0

    chosen = pick_article(candidates, interests=INTERESTS)
    if not chosen:
        send_no_articles_email()
        return 0

    logger.info("Selected: %s", chosen.get("title", "")[:80])
    send_article_email(chosen)
    append_sent(chosen)
    logger.info("Recorded send for %s", chosen["id"])
    return 0
