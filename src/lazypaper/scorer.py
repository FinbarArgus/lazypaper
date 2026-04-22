"""Score articles by keyword overlap (title, abstract, authors, journal) and pick with softmax."""

from __future__ import annotations

import math
import random
import re
from datetime import datetime, timezone
from typing import Iterable

from .cfg import INTERESTS, SELECTION_TEMPERATURE


def _parse_year(published: str) -> int:
    """Extract a 4-digit year from a published string; returns 0 if none found."""
    m = re.search(r'\b(19|20)\d{2}\b', published or "")
    return int(m.group()) if m else 0


def filter_by_year_range(
    articles: Iterable[dict[str, str]],
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict[str, str]]:
    """Keep articles whose publication year falls within [year_min, year_max].

    Articles with an unparseable year (year == 0) are excluded when either bound is set.
    Both bounds are inclusive. Pass both as None to return all articles unchanged.
    """
    if year_min is None and year_max is None:
        return list(articles)
    out = []
    for a in articles:
        year = _parse_year(a.get("published", ""))
        if year == 0:
            continue  # exclude unknowns when a bound is active
        if year_min is not None and year < year_min:
            continue
        if year_max is not None and year > year_max:
            continue
        out.append(a)
    return out


def _score_extra(article: dict[str, str], extra_weights: dict[str, float] | None) -> float:
    """Additional score from citation count, recency, or page count."""
    if not extra_weights:
        return 0.0
    score = 0.0
    current_year = datetime.now(timezone.utc).year
    for feature, weight in extra_weights.items():
        if feature == "citations":
            try:
                c = max(0, int(article.get("citations", 0) or 0))
            except (ValueError, TypeError):
                c = 0
            score += weight * math.log1p(c)
        elif feature == "recency":
            pub_year = _parse_year(article.get("published", ""))
            if pub_year:
                years_ago = current_year - pub_year
                score += weight * max(0.0, 10.0 - years_ago)
        elif feature == "low_page_count":
            try:
                pc = max(0, int(article.get("page_count", 0) or 0))
            except (ValueError, TypeError):
                pc = 0
            score += weight * max(0.0, 20.0 - pc)
        # Unknown keys are silently ignored.
    return score


def _article_keyword_text(article: dict[str, str]) -> str:
    """Haystack for INTERESTS keyword matching: title, abstract, authors, journal."""
    parts = [
        article.get("title", ""),
        article.get("abstract", ""),
        article.get("authors", ""),
        article.get("journal", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def score_article(
    article: dict[str, str],
    interests: dict[str, int] | None = None,
    extra_weights: dict[str, float] | None = None,
) -> float:
    interests = interests or INTERESTS
    text = _article_keyword_text(article)
    total = 0.0
    for phrase, weight in interests.items():
        if not phrase:
            continue
        total += weight * text.count(phrase.lower())
    total += _score_extra(article, extra_weights)
    return total


def pick_article(
    articles: list[dict[str, str]],
    *,
    interests: dict[str, int] | None = None,
    temperature: float | None = None,
    extra_weights: dict[str, float] | None = None,
) -> dict[str, str] | None:
    """
    Pick one article using softmax probabilities over scores.
    Adds a small floor so every article has nonzero chance.
    """
    if not articles:
        return None
    t = temperature if temperature is not None else SELECTION_TEMPERATURE
    if t <= 0:
        t = 0.01

    scores = [score_article(a, interests, extra_weights) for a in articles]
    adjusted = [s + 0.01 for s in scores]
    m = max(adjusted)
    exps = [math.exp((s - m) / t) for s in adjusted]
    ssum = sum(exps)
    weights = [e / ssum for e in exps]
    return random.choices(articles, weights=weights, k=1)[0]


def pick_articles(
    articles: list[dict[str, str]],
    n: int,
    *,
    interests: dict[str, int] | None = None,
    temperature: float | None = None,
    extra_weights: dict[str, float] | None = None,
) -> list[dict[str, str]]:
    """Pick up to n distinct articles, each with softmax on the remaining pool (no replacement)."""
    if n < 1 or not articles:
        return []
    pool = list(articles)
    out: list[dict[str, str]] = []
    for _ in range(min(n, len(pool))):
        one = pick_article(pool, interests=interests, temperature=temperature, extra_weights=extra_weights)
        if not one:
            break
        out.append(one)
        aid = one.get("id")
        pool = [a for a in pool if a.get("id") != aid]
    return out


def filter_unsent(articles: Iterable[dict[str, str]], sent_ids: set[str]) -> list[dict[str, str]]:
    return [a for a in articles if a.get("id") and a["id"] not in sent_ids]


def article_hit_exclusion(article: dict[str, str], exclusions: list[str] | tuple[str, ...] | set[str] | None) -> bool:
    """True if any exclusion phrase (case-insensitive substring) appears in abstract or keywords."""
    if not exclusions:
        return False
    abstract = (article.get("abstract") or "").lower()
    keywords = (article.get("keywords") or "").lower()
    text = f"{abstract} {keywords}"
    for phrase in exclusions:
        p = (phrase or "").strip().lower()
        if p and p in text:
            return True
    return False


def filter_excluded(articles: Iterable[dict[str, str]], exclusions: list[str] | None) -> list[dict[str, str]]:
    if not exclusions:
        return list(articles)
    ex = [e.strip() for e in exclusions if (e or "").strip()]
    if not ex:
        return list(articles)
    return [a for a in articles if not article_hit_exclusion(a, ex)]
