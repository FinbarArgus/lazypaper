"""Unit tests for fetcher DOI/citation enrichment helpers."""

from __future__ import annotations

from types import SimpleNamespace

import lazypaper.fetcher as fetcher


def test_extract_doi_accepts_common_formats() -> None:
    assert fetcher._extract_doi("https://doi.org/10.1000/XYZ.123") == "10.1000/xyz.123"
    assert fetcher._extract_doi("doi:10.1016/j.cell.2020.01.001") == "10.1016/j.cell.2020.01.001"


def test_extract_doi_strips_trailing_punctuation() -> None:
    assert fetcher._extract_doi("(10.1038/s41586-020-2649-2).") == "10.1038/s41586-020-2649-2"


def test_fetch_articles_for_source_uses_openalex_citation_count(monkeypatch) -> None:
    source = {"journal": "Test Journal", "rss": "https://example.com/feed"}

    entry = SimpleNamespace(
        link="https://doi.org/10.1000/test-doi",
        title="A test paper",
        summary="Some summary",
        authors=[{"name": "A Author"}],
        published="2024-01-01",
    )

    monkeypatch.setattr(fetcher, "_fetch_feed_xml", lambda _url: "<rss />")
    monkeypatch.setattr(fetcher.feedparser, "parse", lambda _xml_or_url: SimpleNamespace(entries=[entry], bozo=False))
    monkeypatch.setattr(fetcher, "_openalex_citation_count_for_doi", lambda _doi: 42)

    articles = fetcher.fetch_articles_for_source(source)

    assert len(articles) == 1
    assert articles[0]["citations"] == "42"
    assert articles[0]["page_count"] == "0"


def test_fetch_articles_for_source_defaults_to_10_when_unresolved(monkeypatch) -> None:
    source = {"journal": "Test Journal", "rss": "https://example.com/feed"}

    entry = SimpleNamespace(
        link="https://example.com/article-no-doi",
        title="Paper without DOI",
        summary="No DOI here",
        authors=[{"name": "A Author"}],
        published="2024-01-01",
    )

    monkeypatch.setattr(fetcher, "_fetch_feed_xml", lambda _url: "<rss />")
    monkeypatch.setattr(fetcher.feedparser, "parse", lambda _xml_or_url: SimpleNamespace(entries=[entry], bozo=False))

    articles = fetcher.fetch_articles_for_source(source)

    assert len(articles) == 1
    assert articles[0]["citations"] == "10"
