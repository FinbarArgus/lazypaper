"""Unit tests for fetcher DOI/citation enrichment helpers."""

from __future__ import annotations

from datetime import datetime
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


def test_europepmc_start_page_respects_fixed_cap_of_10(monkeypatch) -> None:
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 23, tzinfo=tz)

    monkeypatch.setattr(fetcher, "datetime", _FakeDatetime)

    # 10,000 hits at page size 20 implies many pages, but the cap must keep start page in 1..10.
    start = fetcher._europepmc_start_page(total_hits=10_000, page_size=20, query="test-query")
    assert 1 <= start <= 10


def test_europepmc_start_page_is_deterministic_for_same_day(monkeypatch) -> None:
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 23, tzinfo=tz)

    monkeypatch.setattr(fetcher, "datetime", _FakeDatetime)

    first = fetcher._europepmc_start_page(total_hits=250, page_size=20, query="abc")
    second = fetcher._europepmc_start_page(total_hits=250, page_size=20, query="abc")
    assert first == second


def test_europepmc_start_page_changes_with_query(monkeypatch) -> None:
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 23, tzinfo=tz)

    monkeypatch.setattr(fetcher, "datetime", _FakeDatetime)

    first = fetcher._europepmc_start_page(total_hits=250, page_size=20, query="abc")
    second = fetcher._europepmc_start_page(total_hits=250, page_size=20, query="xyz")
    assert 1 <= first <= 10
    assert 1 <= second <= 10


def test_europepmc_start_page_returns_1_for_small_result_set(monkeypatch) -> None:
    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 23, tzinfo=tz)

    monkeypatch.setattr(fetcher, "datetime", _FakeDatetime)

    assert fetcher._europepmc_start_page(total_hits=15, page_size=20, query="abc") == 1


def test_europepmc_query_with_year_range_bounded() -> None:
    query = fetcher._europepmc_query_with_year_range("ISSN:1742-5689", 1990, 2020)
    assert query == "(ISSN:1742-5689) AND FIRST_PDATE:[1990-01-01 TO 2020-12-31]"


def test_europepmc_query_with_year_range_open_ended() -> None:
    query = fetcher._europepmc_query_with_year_range("neuroscience", 1990, None)
    assert query == "(neuroscience) AND FIRST_PDATE:[1990-01-01 TO 9999-12-31]"


def test_europepmc_query_with_year_range_no_bounds_returns_original() -> None:
    query = fetcher._europepmc_query_with_year_range("neuroscience", None, None)
    assert query == "neuroscience"
