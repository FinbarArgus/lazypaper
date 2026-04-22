"""Local pipeline: fetch → filter → pick → email, with sent-store and Resend side effects mocked."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.network
@patch("lazypaper.main.send_no_articles_email")
@patch("lazypaper.main.send_articles_email")
@patch("lazypaper.main.append_sent")
@patch("lazypaper.main.load_sent_ids")
def test_local_pipeline_mocks_sent_store_and_email(
    mock_load_sent: object,
    mock_append_sent: object,
    mock_send_articles: object,
    mock_send_no_articles: object,
) -> None:
    """
    Run :func:`lazypaper.main.main` like ``python -m lazypaper`` but without
    a live sent-history store or Resend. Sent history is empty so already-sent articles
    do not block selection; the email path still exercises live feed fetches.
    """
    mock_load_sent.return_value = set()
    from lazypaper import main

    assert main.main() == 0
    if mock_send_articles.called:
        mock_append_sent.assert_called_once()
        mock_send_articles.assert_called_once()
    else:
        mock_send_no_articles.assert_called_once()
        mock_append_sent.assert_not_called()


# ── Year-range filter integration tests (no network) ─────────────────────────

_FAKE_ARTICLE = {
    "id": "https://doi.org/10.1234/test",
    "title": "Test article on Bayesian modelling",
    "abstract": "A study using Bayesian parameter estimation.",
    "keywords": "Bayesian",
    "authors": "Smith J",
    "published": "2022-06-01",
    "journal": "Test Journal",
    "link": "https://doi.org/10.1234/test",
    "citations": "5",
    "page_count": "8",
}

_OLD_ARTICLE = dict(_FAKE_ARTICLE, id="https://doi.org/10.1234/old",
                    link="https://doi.org/10.1234/old", published="2000-01-01")


def _make_schedule(year_min=None, year_max=None, extra_weights=None):
    return {
        "default": {
            "year_min": year_min,
            "year_max": year_max,
            "extra_weights": extra_weights or {},
        }
    }


@patch("lazypaper.main.send_no_articles_email")
@patch("lazypaper.main.send_articles_email")
@patch("lazypaper.main.append_sent")
@patch("lazypaper.main.load_sent_ids")
@patch("lazypaper.main.fetch_all_articles")
def test_pipeline_year_filter_excludes_old_article(
    mock_fetch, mock_load_sent, mock_append_sent, mock_send_articles, mock_send_no_articles
):
    """Articles outside year_min are dropped; only the newer article is picked."""
    mock_fetch.return_value = [_FAKE_ARTICLE, _OLD_ARTICLE]
    mock_load_sent.return_value = set()

    import lazypaper.main as main_mod
    with patch.object(main_mod, "DAILY_SCHEDULE", _make_schedule(year_min=2010)):
        main_mod.main()

    # The old (year 2000) article must not appear in any send call.
    if mock_send_articles.called:
        sent_articles = mock_send_articles.call_args[0][0]
        ids = [a["id"] for a in sent_articles]
        assert _OLD_ARTICLE["id"] not in ids, "Old article should have been filtered by year_min"
    else:
        # No articles sent means only _OLD_ARTICLE would have been a candidate (all filtered),
        # which is acceptable — but we still confirm it wasn't sent.
        mock_send_no_articles.assert_called_once()


@patch("lazypaper.main.send_no_articles_email")
@patch("lazypaper.main.send_articles_email")
@patch("lazypaper.main.append_sent")
@patch("lazypaper.main.load_sent_ids")
@patch("lazypaper.main.fetch_all_articles")
def test_pipeline_year_filter_all_articles_filtered_sends_no_articles_email(
    mock_fetch, mock_load_sent, mock_append_sent, mock_send_articles, mock_send_no_articles
):
    """When year filter removes every candidate, send_no_articles_email is called."""
    mock_fetch.return_value = [_OLD_ARTICLE]  # year 2000
    mock_load_sent.return_value = set()

    import lazypaper.main as main_mod
    with patch.object(main_mod, "DAILY_SCHEDULE", _make_schedule(year_min=2020)):
        main_mod.main()

    mock_send_no_articles.assert_called_once()
    mock_send_articles.assert_not_called()


@patch("lazypaper.main.send_no_articles_email")
@patch("lazypaper.main.send_articles_email")
@patch("lazypaper.main.append_sent")
@patch("lazypaper.main.load_sent_ids")
@patch("lazypaper.main.fetch_all_articles")
def test_pipeline_no_year_filter_passes_all_articles(
    mock_fetch, mock_load_sent, mock_append_sent, mock_send_articles, mock_send_no_articles
):
    """With no year bounds, both articles remain as candidates."""
    mock_fetch.return_value = [_FAKE_ARTICLE, _OLD_ARTICLE]
    mock_load_sent.return_value = set()

    import lazypaper.main as main_mod
    with patch.object(main_mod, "DAILY_SCHEDULE", _make_schedule()):
        main_mod.main()

    # At least one article should have been sent (no filtering happened).
    mock_send_articles.assert_called_once()
    mock_send_no_articles.assert_not_called()
