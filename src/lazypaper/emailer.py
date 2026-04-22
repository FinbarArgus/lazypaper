"""Send digest email via Resend."""

from __future__ import annotations

import html
import os

import resend
from resend.exceptions import ResendError

from .cfg import DEFAULT_RESEND_FROM, RECIPIENT_EMAIL


def _env_or_default(name: str, default: str) -> str:
    """GitHub Actions sets missing secrets to empty env vars; treat those like unset."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    stripped = raw.strip()
    return stripped if stripped else default


def _send_with_friendly_errors(params: dict) -> None:
    try:
        resend.Emails.send(params)
    except ResendError as e:
        msg = str(e) or type(e).__name__
        from_addr = params.get("from", "")
        to_addrs = ", ".join(params.get("to", []) or [])
        hint = ""
        lower = msg.lower()
        if "domain" in lower and "invalid" in lower:
            hint = (
                "\nThis usually means Resend does not accept the 'From' domain for this account. "
                "Fix by either:\n"
                "  1) Verify your own domain in the Resend dashboard (Domains -> Add), add its "
                "DNS records, then set RESEND_FROM to 'Your Name <you@your-verified-domain>'; or\n"
                "  2) Keep the sandbox sender onboarding@resend.dev and make sure RECIPIENT_EMAIL "
                "(or LAZYPAPER_TO) is the same email you signed up to Resend with."
            )
        raise RuntimeError(
            f"Resend rejected the message (from={from_addr!r}, to=[{to_addrs}]): {msg}{hint}"
        ) from e


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


def _describe_daily(daily: dict | None) -> str:
    """Build a short natural-language description of today's selection criteria.

    Examples:
      {extra_weights: {citations: 2}, year_min: 1990, year_max: 2020}
        -> "high citation pick from 1990\u20132020"
      {extra_weights: {recency: 1}}
        -> "recent publication pick"
      {extra_weights: {citations: 1, low_page_count: 2}}
        -> "short paper, high citation pick"
      {} -> "pick"
    """
    _WEIGHT_PHRASES: dict[str, str] = {
        "citations": "high citation",
        "recency": "recent publication",
        "low_page_count": "short paper",
    }
    if not daily:
        return "pick"

    extra = daily.get("extra_weights") or {}
    year_min = daily.get("year_min")
    year_max = daily.get("year_max")

    # Build qualifier from extra_weights sorted by descending weight value.
    qualifiers = [
        _WEIGHT_PHRASES[k]
        for k, _ in sorted(extra.items(), key=lambda kv: -kv[1])
        if k in _WEIGHT_PHRASES
    ]
    qualifier = ", ".join(qualifiers)

    # Build year-range suffix.
    if year_min and year_max:
        year_suffix = f" from {year_min}\u2013{year_max}"
    elif year_min:
        year_suffix = f" from {year_min}"
    elif year_max:
        year_suffix = f" up to {year_max}"
    else:
        year_suffix = ""

    parts = [qualifier, "pick"] if qualifier else ["pick"]
    return " ".join(parts) + year_suffix


def build_html_digest(articles: list[dict[str, str]], daily: dict | None = None) -> str:
    n = len(articles)
    description = _describe_daily(daily)
    # _describe_daily ends with "pick[…]"; pluralise the word "pick" for multiple articles.
    heading_desc = description.replace("pick", "picks", 1) if n > 1 else description
    heading = f"Today&apos;s {heading_desc}"
    sections = "".join(_article_html_section(a) for a in articles)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: system-ui, sans-serif; line-height: 1.5; max-width: 640px;">
  <h1 style="font-size: 1.25rem;">{heading}</h1>
{sections}
</body>
</html>"""


def send_articles_email(articles: list[dict[str, str]], daily: dict | None = None) -> None:
    if not articles:
        raise ValueError("articles must be non-empty")

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set.")

    resend.api_key = api_key
    from_addr = _env_or_default("RESEND_FROM", DEFAULT_RESEND_FROM)
    if len(articles) == 1:
        subject = f"LazyPaper: {articles[0].get('title', 'Paper')[:120]}"
    else:
        subject = f"LazyPaper: {len(articles)} articles for today"

    params: dict = {
        "from": from_addr,
        "to": [_env_or_default("LAZYPAPER_TO", RECIPIENT_EMAIL)],
        "subject": subject,
        "html": build_html_digest(articles, daily),
    }

    _send_with_friendly_errors(params)


def send_no_articles_email() -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set.")

    resend.api_key = api_key
    from_addr = _env_or_default("RESEND_FROM", DEFAULT_RESEND_FROM)
    body = (
        "<p>No new articles were available from the configured feeds after removing "
        "ones already sent. Try adding feeds in <code>config.py</code> or adjusting "
        "<code>EXCLUSIONS</code>.</p>"
    )
    _send_with_friendly_errors(
        {
            "from": from_addr,
            "to": [_env_or_default("LAZYPAPER_TO", RECIPIENT_EMAIL)],
            "subject": "LazyPaper: no new article today",
            "html": body,
        }
    )
