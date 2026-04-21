"""Send digest email via Resend."""

from __future__ import annotations

import html
import os

import resend

from .cfg import DEFAULT_RESEND_FROM, RECIPIENT_EMAIL, RESEND_API_KEY_FROM_FILE


def _resend_api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY") or RESEND_API_KEY_FROM_FILE


def _article_html_section(article: dict[str, str]) -> str:
    title = html.escape(article.get("title") or "")
    journal = html.escape(article.get("journal") or "")
    authors = html.escape(article.get("authors") or "")
    abstract = html.escape(article.get("abstract") or "")
    link = html.escape(article.get("link") or "")

    abstract_block = f"<p>{abstract}</p>" if abstract else "<p><em>No abstract in feed.</em></p>"
    authors_block = f"<p><strong>Authors:</strong> {authors}</p>" if authors else ""

    return f"""
  <section style="margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid #e5e5e5;">
  <h2 style="font-size: 1.1rem; margin-top: 0;">{title}</h2>
  <p><strong>Journal:</strong> {journal}</p>
  {authors_block}
  {abstract_block}
  <p><a href="{link}">Open article</a></p>
  </section>"""


def build_html_digest(articles: list[dict[str, str]]) -> str:
    n = len(articles)
    heading = "Today&apos;s picks" if n > 1 else "Today&apos;s pick"
    sections = "".join(_article_html_section(a) for a in articles)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: system-ui, sans-serif; line-height: 1.5; max-width: 640px;">
  <h1 style="font-size: 1.25rem;">{heading}</h1>
{sections}
</body>
</html>"""


def send_articles_email(articles: list[dict[str, str]]) -> None:
    if not articles:
        raise ValueError("articles must be non-empty")

    api_key = _resend_api_key()
    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not set (environment variable or user_resend_api_Key file)."
        )

    resend.api_key = api_key
    from_addr = os.environ.get("RESEND_FROM", DEFAULT_RESEND_FROM)
    if len(articles) == 1:
        subject = f"LazyPaper: {articles[0].get('title', 'Paper')[:120]}"
    else:
        subject = f"LazyPaper: {len(articles)} articles for today"

    params: dict = {
        "from": from_addr,
        "to": [os.environ.get("LAZYPAPER_TO", RECIPIENT_EMAIL)],
        "subject": subject,
        "html": build_html_digest(articles),
    }

    resend.Emails.send(params)


def send_no_articles_email() -> None:
    api_key = _resend_api_key()
    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not set (environment variable or user_resend_api_Key file)."
        )

    resend.api_key = api_key
    from_addr = os.environ.get("RESEND_FROM", DEFAULT_RESEND_FROM)
    body = (
        "<p>No new articles were available from the configured feeds after removing "
        "ones already sent. Try adding feeds in <code>config.py</code> or trimming "
        "<code>sent_articles.json</code>.</p>"
    )
    resend.Emails.send(
        {
            "from": from_addr,
            "to": [os.environ.get("LAZYPAPER_TO", RECIPIENT_EMAIL)],
            "subject": "LazyPaper: no new article today",
            "html": body,
        }
    )
