"""Unit tests for scorer helpers: _parse_year, filter_by_year_range, _score_extra."""

from __future__ import annotations

import math

import pytest

from lazypaper.scorer import _parse_year, _score_extra, filter_by_year_range


# ── _parse_year ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("published,expected", [
    ("2023-07-15", 2023),
    ("Mon, 01 Jan 2024 00:00:00 +0000", 2024),
    ("2019", 2019),
    ("", 0),
    ("no year here", 0),
    ("1899-01-01", 0),  # before 1900: not matched by the regex
    ("2099-12-31", 2099),
])
def test_parse_year(published, expected):
    assert _parse_year(published) == expected


# ── filter_by_year_range ──────────────────────────────────────────────────────

def _art(published: str) -> dict:
    return {"id": published, "published": published}


def test_filter_by_year_range_no_bounds_returns_all():
    arts = [_art("2020-01-01"), _art("2024-06-01"), _art("")]
    assert filter_by_year_range(arts) == arts


def test_filter_by_year_range_min_only():
    arts = [_art("2019-01-01"), _art("2021-01-01"), _art("2023-01-01")]
    result = filter_by_year_range(arts, year_min=2021)
    assert [a["published"] for a in result] == ["2021-01-01", "2023-01-01"]


def test_filter_by_year_range_max_only():
    arts = [_art("2019-01-01"), _art("2021-01-01"), _art("2023-01-01")]
    result = filter_by_year_range(arts, year_max=2021)
    assert [a["published"] for a in result] == ["2019-01-01", "2021-01-01"]


def test_filter_by_year_range_both_bounds():
    arts = [_art("2018-01-01"), _art("2020-01-01"), _art("2022-01-01"), _art("2025-01-01")]
    result = filter_by_year_range(arts, year_min=2020, year_max=2022)
    assert [a["published"] for a in result] == ["2020-01-01", "2022-01-01"]


def test_filter_by_year_range_unknown_year_excluded_when_bound_set():
    arts = [_art(""), _art("2022-01-01")]
    result = filter_by_year_range(arts, year_min=2020)
    assert len(result) == 1
    assert result[0]["published"] == "2022-01-01"


def test_filter_by_year_range_unknown_year_kept_when_no_bounds():
    arts = [_art(""), _art("2022-01-01")]
    result = filter_by_year_range(arts)
    assert len(result) == 2


# ── _score_extra ──────────────────────────────────────────────────────────────

def _scored_art(**kwargs) -> dict:
    base = {"id": "x", "published": "2020-01-01", "citations": "0", "page_count": "0"}
    base.update(kwargs)
    return base


def test_score_extra_no_weights_returns_zero():
    assert _score_extra(_scored_art(), None) == 0.0
    assert _score_extra(_scored_art(), {}) == 0.0


def test_score_extra_citations():
    art = _scored_art(citations="9")  # log1p(9) ≈ 2.302
    score = _score_extra(art, {"citations": 1})
    assert math.isclose(score, math.log1p(9), rel_tol=1e-9)


def test_score_extra_citations_bad_value_treated_as_zero():
    art = _scored_art(citations="n/a")
    score = _score_extra(art, {"citations": 5})
    assert score == 0.0


def test_score_extra_recency(monkeypatch):
    # Freeze current year to 2026 so the test is deterministic.
    import lazypaper.scorer as scorer_mod
    from datetime import datetime, timezone

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 23, tzinfo=tz)

    monkeypatch.setattr(scorer_mod, "datetime", _FakeDatetime)
    art = _scored_art(published="2024-01-01")  # 2 years ago → max(0, 10-2) = 8
    score = _score_extra(art, {"recency": 1})
    assert math.isclose(score, 8.0)


def test_score_extra_recency_old_paper_clamped_to_zero(monkeypatch):
    import lazypaper.scorer as scorer_mod
    from datetime import datetime, timezone

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 23, tzinfo=tz)

    monkeypatch.setattr(scorer_mod, "datetime", _FakeDatetime)
    art = _scored_art(published="2010-01-01")  # 16 years ago → max(0, 10-16) = 0
    score = _score_extra(art, {"recency": 10})
    assert score == 0.0


def test_score_extra_low_page_count():
    art = _scored_art(page_count="5")  # max(0, 20-5) = 15
    score = _score_extra(art, {"low_page_count": 2})
    assert math.isclose(score, 30.0)


def test_score_extra_low_page_count_large_clamped():
    art = _scored_art(page_count="25")  # max(0, 20-25) = 0
    score = _score_extra(art, {"low_page_count": 3})
    assert score == 0.0


def test_score_extra_unknown_key_ignored():
    art = _scored_art()
    score = _score_extra(art, {"unknown_signal": 99})
    assert score == 0.0


def test_score_extra_multiple_weights():
    art = _scored_art(citations="0", page_count="10")
    score = _score_extra(art, {"citations": 1, "low_page_count": 1})
    # citations: log1p(0) = 0; low_page_count: max(0, 20-10) * 1 = 10
    assert math.isclose(score, 10.0)
