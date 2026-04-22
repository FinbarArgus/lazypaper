#!/usr/bin/env python3
"""Fetch journal feeds, pick unsent articles, email them, record the send."""

from __future__ import annotations

import datetime
import logging
from urllib.parse import urlparse, urlunparse

from .cfg import DAILY_SCHEDULE, EXCLUSIONS, INTERESTS, PAPERS_PER_DAY
from .emailer import send_articles_email, send_no_articles_email
from .fetcher import fetch_all_articles
from .scorer import filter_by_year_range, filter_excluded, filter_unsent, pick_articles
from .sent_store import append_sent, load_sent_ids

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _resolve_daily(schedule: dict) -> dict:
    """Return the day config for today's UTC weekday, falling back to 'default'."""
    day_name = datetime.datetime.now(datetime.timezone.utc).strftime("%A").lower()
    cfg = schedule.get(day_name) or schedule.get("default") or {}
    return {
        "year_min": cfg.get("year_min"),
        "year_max": cfg.get("year_max"),
        "extra_weights": cfg.get("extra_weights") or {},
    }


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


def main() -> int:
    sent = load_sent_ids()
    daily = _resolve_daily(DAILY_SCHEDULE)
    logger.info("Fetching feeds…")
    raw = fetch_all_articles(year_min=daily["year_min"], year_max=daily["year_max"])
    articles = _dedupe_articles(raw)
    logger.info("Collected %s unique articles from feeds", len(articles))
    candidates = filter_unsent(articles, sent)
    logger.info("%s candidates after removing %s already sent", len(candidates), len(sent))
    before_ex = len(candidates)
    candidates = filter_excluded(candidates, EXCLUSIONS)
    if before_ex > len(candidates):
        logger.info(
            "Excluded %s article(s) matching EXCLUSIONS (abstract/keywords), %s candidates remain",
            before_ex - len(candidates),
            len(candidates),
        )

    before_yr = len(candidates)
    candidates = filter_by_year_range(candidates, daily["year_min"], daily["year_max"])
    if before_yr > len(candidates):
        logger.info(
            "Year filter [%s–%s] dropped %s article(s), %s candidates remain",
            daily["year_min"] or "–∞",
            daily["year_max"] or "+∞",
            before_yr - len(candidates),
            len(candidates),
        )

    if not candidates:
        logger.warning("No unsent articles; sending notice email")
        send_no_articles_email()
        return 0

    n = max(1, PAPERS_PER_DAY)
    chosen = pick_articles(candidates, n, interests=INTERESTS, extra_weights=daily["extra_weights"])
    if not chosen:
        send_no_articles_email()
        return 0

    for i, a in enumerate(chosen):
        logger.info("Selected [%s/%s]: %s", i + 1, len(chosen), a.get("title", "")[:80])
    send_articles_email(chosen, daily)
    append_sent(chosen)
    for a in chosen:
        logger.info("Recorded send for %s", a["id"])
    return 0
