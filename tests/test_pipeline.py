"""Local pipeline: fetch → filter → pick → email, with DB and Resend side effects mocked."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.network
@patch("lazypaper.main.send_no_articles_email")
@patch("lazypaper.main.send_articles_email")
@patch("lazypaper.main.append_sent")
@patch("lazypaper.main.load_sent_ids")
def test_local_pipeline_mocks_postgres_and_email(
    mock_load_sent: object,
    mock_append_sent: object,
    mock_send_articles: object,
    mock_send_no_articles: object,
) -> None:
    """
    Run :func:`lazypaper.main.main` like ``python -m lazypaper`` but without
    ``DATABASE_URL`` or Resend. Sent history is empty so already-sent articles
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
