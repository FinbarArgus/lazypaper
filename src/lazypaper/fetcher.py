"""Fetch and normalise articles from configured RSS feeds."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

from .cfg import SOURCES

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


def _entry_keywords(entry: Any) -> str:
    """Tag/category / DC subject text from a feed entry (for EXCLUSIONS matching)."""
    parts: list[str] = []
    for t in getattr(entry, "tags", None) or []:
        if isinstance(t, dict):
            term = t.get("term") or t.get("label")
            if term:
                parts.append(str(term))
        else:
            term = getattr(t, "term", None) or getattr(t, "label", None)
            if term:
                parts.append(str(term))
    for attr in ("category", "dc_subject", "subject", "itunes_keywords"):
        v = getattr(entry, attr, None)
        if v and isinstance(v, str) and v.strip():
            parts.append(v.strip())
    return ", ".join(parts)


def _europepmc_mesh_keywords_text(result: ET.Element) -> str:
    """Mesh / keyword-like strings from a Europe PMC <result> node."""
    out: list[str] = []
    for el in result.iter():
        tag = _xml_localname(el.tag)
        if tag == "descriptorName" and el.text and el.text.strip():
            out.append(el.text.strip())
        if tag in ("keyword",) and el.text and el.text.strip():
            out.append(el.text.strip())
    return ", ".join(out)


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
        keywords = _europepmc_mesh_keywords_text(el)

        citations_raw = _xml_child_text(el, "citedByCount")
        try:
            citations = str(max(0, int(citations_raw)))
        except (ValueError, TypeError):
            citations = "0"

        page_info = _xml_child_text(el, "pageInfo")
        page_count = "0"
        if page_info:
            import re as _re
            m = _re.fullmatch(r"(\d+)\s*-\s*(\d+)", page_info.strip())
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                page_count = str(max(0, end - start + 1))

        out.append(
            {
                "id": link,
                "title": title,
                "abstract": abstract,
                "keywords": keywords,
                "authors": authors,
                "published": published,
                "journal": journal,
                "link": link,
                "citations": citations,
                "page_count": page_count,
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


def fetch_articles_for_source(source: dict[str, str]) -> list[dict[str, str]]:
    """Return normalised article dicts for a single entry in the same shape as :func:`fetch_all_articles`."""
    out: list[dict[str, str]] = []
    journal = source["journal"]
    if source.get("europepmc_query"):
        return _fetch_europepmc_articles(journal, str(source["europepmc_query"]))

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
        keywords = _entry_keywords(entry)
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
                "keywords": keywords,
                "authors": authors,
                "published": published,
                "journal": journal,
                "link": link,
                "citations": "0",
                "page_count": "0",
            }
        )
    return out


def fetch_all_articles() -> list[dict[str, str]]:
    """Return normalised article dicts from all configured feeds."""
    out: list[dict[str, str]] = []
    for source in SOURCES:
        out.extend(fetch_articles_for_source(source))
    return out
