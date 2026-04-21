"""Fetch and normalise articles from configured RSS feeds."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

from config import SOURCES

logger = logging.getLogger(__name__)

# Many publisher CDNs return 403 to non-browser user agents; identify as a normal feed client.
USER_AGENT = (
    "Mozilla/5.0 (compatible; lazypaper/1.0; +https://github.com; RSS reader; "
    "like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _strip_html(html: str | None) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def _entry_link(entry: Any) -> str:
    if getattr(entry, "link", None):
        return str(entry.link).strip()
    links = getattr(entry, "links", None) or []
    for link in links:
        if link.get("rel") == "alternate" and link.get("href"):
            return str(link["href"]).strip()
    if links and links[0].get("href"):
        return str(links[0]["href"]).strip()
    return ""


def _entry_authors(entry: Any) -> str:
    if getattr(entry, "author", None):
        return str(entry.author).strip()
    if getattr(entry, "authors", None):
        parts = []
        for a in entry.authors:
            if isinstance(a, dict) and a.get("name"):
                parts.append(str(a["name"]))
            elif isinstance(a, str):
                parts.append(a)
        return ", ".join(parts)
    return ""


def _entry_summary(entry: Any) -> str:
    for attr in ("summary", "description", "content"):
        val = getattr(entry, attr, None)
        if not val:
            continue
        if attr == "content" and isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, dict) and first.get("value"):
                return _strip_html(str(first["value"]))
        if isinstance(val, str):
            return _strip_html(val)
    return ""


def _xml_localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _xml_child_text(parent: ET.Element, name: str) -> str:
    for child in parent:
        if _xml_localname(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _fetch_europepmc_articles(journal: str, query: str, page_size: int = 50) -> list[dict[str, str]]:
    """Recent articles from Europe PMC search API (XML)."""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": query,
        "resultType": "core",
        "pageSize": str(page_size),
        "format": "xml",
    }
    try:
        r = requests.get(
            url,
            params=params,
            timeout=45,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml",
            },
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Europe PMC fetch failed (%s): %s", query, e)
        return []

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        logger.warning("Europe PMC XML parse error (%s): %s", query, e)
        return []

    out: list[dict[str, str]] = []
    for el in root.iter():
        if _xml_localname(el.tag) != "result":
            continue
        title = _xml_child_text(el, "title") or "(no title)"
        doi = _xml_child_text(el, "doi")
        link = f"https://doi.org/{doi}" if doi else ""
        if not link:
            pmid = _xml_child_text(el, "pmid")
            if pmid:
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        if not link:
            continue
        abstract = _xml_child_text(el, "abstractText")
        authors = _xml_child_text(el, "authorString")
        published = _xml_child_text(el, "firstPublicationDate")

        out.append(
            {
                "id": link,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "published": published,
                "journal": journal,
                "link": link,
            }
        )
    return out


def _fetch_feed_xml(url: str) -> str | None:
    try:
        r = requests.get(
            url,
            timeout=45,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            },
        )
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        logger.warning("HTTP fetch failed for %s: %s", url, e)
        return None


def fetch_all_articles() -> list[dict[str, str]]:
    """Return normalised article dicts from all configured feeds."""
    out: list[dict[str, str]] = []
    for source in SOURCES:
        journal = source["journal"]
        if source.get("europepmc_query"):
            out.extend(_fetch_europepmc_articles(journal, str(source["europepmc_query"])))
            continue

        url = source["rss"]
        xml = _fetch_feed_xml(url)
        if xml:
            parsed = feedparser.parse(xml)
        else:
            parsed = feedparser.parse(url)

        if getattr(parsed, "bozo", False) and not parsed.entries:
            logger.warning(
                "Parse issues for %s (%s): %s",
                journal,
                url,
                getattr(parsed, "bozo_exception", None),
            )

        for entry in parsed.entries:
            link = _entry_link(entry)
            if not link:
                continue
            title = _strip_html(getattr(entry, "title", None) or "") or "(no title)"
            abstract = _entry_summary(entry)
            authors = _entry_authors(entry)
            published = ""
            if getattr(entry, "published", None):
                published = str(entry.published)
            elif getattr(entry, "updated", None):
                published = str(entry.updated)

            out.append(
                {
                    "id": link,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "published": published,
                    "journal": journal,
                    "link": link,
                }
            )
    return out
