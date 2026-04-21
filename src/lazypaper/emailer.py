"""Send digest email via Resend."""

from __future__ import annotations

import html
import os

import resend

from .config import DEFAULT_RESEND_FROM, RECIPIENT_EMAIL


def build_html(article: dict[str, str]) -> str:
    title = html.escape(article.get("title") or "")
    journal = html.escape(article.get("journal") or "")
    authors = html.escape(article.get("authors") or "")
    abstract = html.escape(article.get("abstract") or "")
    link = html.escape(article.get("link") or "")

    abstract_block = f"<p>{abstract}</p>" if abstract else "<p><em>No abstract in feed.</em></p>"
    authors_block = f"<p><strong>Authors:</strong> {authors}</p>" if authors else ""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: system-ui, sans-serif; line-height: 1.5; max-width: 640px;">
  <h1 style="font-size: 1.25rem;">Today&apos;s pick</h1>
  <h2 style="font-size: 1.1rem;">{title}</h2>
  <p><strong>Journal:</strong> {journal}</p>
  {authors_block}
  {abstract_block}
  <p><a href="{link}">Open article</a></p>
</body>
</html>"""


def send_article_email(article: dict[str, str]) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set.")

    resend.api_key = api_key
    from_addr = os.environ.get("RESEND_FROM", DEFAULT_RESEND_FROM)
    subject = f"LazyPaper: {article.get('title', 'Paper')[:120]}"

    params: dict = {
        "from": from_addr,
        "to": [os.environ.get("LAZYPAPER_TO", RECIPIENT_EMAIL)],
        "subject": subject,
        "html": build_html(article),
    }

    resend.Emails.send(params)


def send_no_articles_email() -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set.")

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
