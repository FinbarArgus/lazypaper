"""Score articles by keyword overlap and pick one with softmax-weighted randomness."""

from __future__ import annotations

import math
import random
from typing import Iterable

from config import INTERESTS, SELECTION_TEMPERATURE


def score_article(article: dict[str, str], interests: dict[str, int] | None = None) -> float:
    interests = interests or INTERESTS
    text = f"{article.get('title', '')} {article.get('abstract', '')}".lower()
    total = 0.0
    for phrase, weight in interests.items():
        if not phrase:
            continue
        total += weight * text.count(phrase.lower())
    return total


def pick_article(
    articles: list[dict[str, str]],
    *,
    interests: dict[str, int] | None = None,
    temperature: float | None = None,
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

    scores = [score_article(a, interests) for a in articles]
    adjusted = [s + 0.01 for s in scores]
    m = max(adjusted)
    exps = [math.exp((s - m) / t) for s in adjusted]
    ssum = sum(exps)
    weights = [e / ssum for e in exps]
    return random.choices(articles, weights=weights, k=1)[0]


def filter_unsent(articles: Iterable[dict[str, str]], sent_ids: set[str]) -> list[dict[str, str]]:
    return [a for a in articles if a.get("id") and a["id"] not in sent_ids]
