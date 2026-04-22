"""Per-feed smoke tests: each source in the repo :file:`config.py` must return at least one normalised article."""

from __future__ import annotations

import pytest

from lazypaper.cfg import SOURCES
from lazypaper.fetcher import fetch_articles_for_source

# Keys every normalised article dict from the fetcher is expected to have.
_ARTICLE_KEYS = {
    "id",
    "title",
    "abstract",
    "keywords",
    "authors",
    "published",
    "journal",
    "link",
    "citations",
    "page_count",
}


def _source_id(source: dict[str, str]) -> str:
    return source.get("journal") or "unknown"


@pytest.mark.network
@pytest.mark.parametrize("source", SOURCES, ids=[_source_id(s) for s in SOURCES])
def test_each_config_source_yields_at_least_one_article(source: dict[str, str]) -> None:
    attempts = 3 if source.get("europepmc_query") else 1
    articles: list[dict[str, str]] = []
    for _ in range(attempts):
        articles = fetch_articles_for_source(source)
        if articles:
            break

    if not articles and source.get("europepmc_query"):
        pytest.xfail(
            f"Europe PMC unavailable or timed out after {attempts} attempts for {source['europepmc_query']}"
        )

    assert len(articles) >= 1, f"expected at least one article for source {source!r}"
    a = articles[0]
    assert set(a.keys()) == _ARTICLE_KEYS
    assert a["id"]
    assert a["link"] == a["id"]
    assert a["journal"] == source["journal"]
