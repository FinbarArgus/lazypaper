"""Fetch and normalise articles from configured RSS feeds."""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cfg import SOURCES

logger = logging.getLogger(__name__)

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_UNKNOWN_CITATIONS_DEFAULT = 10
_EUROPEPMC_MAX_PAGE = 10
_EUROPEPMC_PAGE_WINDOW = 3

# Many publisher CDNs return 403 to non-browser user agents; identify as a normal feed client.
USER_AGENT = (
    "Mozilla/5.0 (compatible; lazypaper/1.0; +https://github.com; RSS reader; "
    "like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Retry up to 3 times on transient server errors (5xx) and connection failures,
# with exponential backoff: 0 s, 2 s, 4 s between attempts.
_RETRY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist={500, 502, 503, 504},
    raise_on_status=False,
)


def _session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


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


def _extract_doi(text: str | None) -> str | None:
    if not text:
        return None
    m = _DOI_RE.search(text)
    if not m:
        return None
    # Some feeds include trailing punctuation around DOI-like text.
    return m.group(0).rstrip(".,;:)]\"'").lower()


def _entry_doi(entry: Any, *, link: str, abstract: str, title: str) -> str | None:
    candidates: list[str] = []

    for attr in ("doi", "dc_identifier", "prism_doi", "id"):
        v = getattr(entry, attr, None)
        if isinstance(v, str) and v.strip():
            candidates.append(v)

    if link:
        candidates.append(link)
    if title:
        candidates.append(title)
    if abstract:
        candidates.append(abstract)

    for doi in (_extract_doi(c) for c in candidates):
        if doi:
            return doi
    return None


def _openalex_citation_count_for_doi(doi: str) -> int | None:
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"doi:https://doi.org/{doi}",
        "select": "cited_by_count",
        "per-page": "1",
    }
    try:
        r = _session().get(
            url,
            params=params,
            timeout=30,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        logger.debug("OpenAlex lookup failed for DOI %s: %s", doi, e)
        return None

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or not results:
        return None

    raw = results[0].get("cited_by_count") if isinstance(results[0], dict) else None
    if isinstance(raw, int):
        return max(0, raw)
    return None


def _parse_year_from_published(published: str) -> int:
    m = re.search(r"\b(19|20)\d{2}\b", published or "")
    return int(m.group()) if m else 0


def _in_year_range(article: dict[str, str], year_min: int | None, year_max: int | None) -> bool:
    if year_min is None and year_max is None:
        return True
    year = _parse_year_from_published(article.get("published", ""))
    if year == 0:
        return False
    if year_min is not None and year < year_min:
        return False
    if year_max is not None and year > year_max:
        return False
    return True


def _stable_rotation_seed(*parts: str) -> int:
    seed = 0
    for part in parts:
        for ch in part:
            seed = (seed * 131 + ord(ch)) % 2_147_483_647
    return seed


def _europepmc_start_page(total_hits: int, page_size: int, query: str) -> int:
    if total_hits <= 0 or page_size <= 0:
        return 1
    total_pages = max(1, math.ceil(total_hits / page_size))
    capped_pages = min(_EUROPEPMC_MAX_PAGE, total_pages)
    # Rotate deterministically across days and queries to avoid repeatedly consuming page 1.
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    seed = _stable_rotation_seed(query, str(day_of_year))
    return 1 + (seed % capped_pages)


def _fetch_europepmc_page(
    *,
    url: str,
    query: str,
    result_type: str,
    size: str,
    fmt: str,
    accept: str,
    timeout_s: int,
    page: int,
) -> tuple[list[dict[str, str]], int]:
    params = {
        "query": query,
        "resultType": result_type,
        "pageSize": size,
        "format": fmt,
        "page": str(page),
    }
    r = _session().get(
        url,
        params=params,
        timeout=timeout_s,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    r.raise_for_status()

    if fmt == "xml":
        return _parse_europepmc_xml(journal="", raw_xml=r.text)

    payload = r.json()
    return _parse_europepmc_json(journal="", payload=payload)


def _xml_localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _xml_child_text(parent: ET.Element, name: str) -> str:
    for child in parent:
        if _xml_localname(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _europepmc_article(
    *,
    journal: str,
    title: str,
    doi: str,
    pmid: str,
    abstract: str,
    authors: str,
    published: str,
    citations_raw: Any,
    page_info: str,
    keywords: str,
) -> dict[str, str] | None:
    link = f"https://doi.org/{doi}" if doi else ""
    if not link and pmid:
        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    if not link:
        return None

    try:
        citations = str(max(0, int(citations_raw)))
    except (ValueError, TypeError):
        citations = "0"

    page_count = "0"
    if page_info:
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", page_info.strip())
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            page_count = str(max(0, end - start + 1))

    return {
        "id": link,
        "title": title or "(no title)",
        "abstract": abstract,
        "keywords": keywords,
        "authors": authors,
        "published": published,
        "journal": journal,
        "link": link,
        "citations": citations,
        "page_count": page_count,
    }


def _parse_europepmc_xml(journal: str, raw_xml: str) -> tuple[list[dict[str, str]], int]:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return [], 0

    hit_count = 0
    for el in root.iter():
        if _xml_localname(el.tag) == "hitCount":
            try:
                hit_count = int((el.text or "").strip())
            except ValueError:
                hit_count = 0
            break

    out: list[dict[str, str]] = []
    for el in root.iter():
        if _xml_localname(el.tag) != "result":
            continue

        article = _europepmc_article(
            journal=journal,
            title=_xml_child_text(el, "title"),
            doi=_xml_child_text(el, "doi"),
            pmid=_xml_child_text(el, "pmid"),
            abstract=_xml_child_text(el, "abstractText"),
            authors=_xml_child_text(el, "authorString"),
            published=_xml_child_text(el, "firstPublicationDate"),
            citations_raw=_xml_child_text(el, "citedByCount"),
            page_info=_xml_child_text(el, "pageInfo"),
            keywords=_europepmc_mesh_keywords_text(el),
        )
        if article:
            out.append(article)

    return out, hit_count


def _parse_europepmc_json(journal: str, payload: Any) -> tuple[list[dict[str, str]], int]:
    if not isinstance(payload, dict):
        return [], 0

    try:
        hit_count = int(payload.get("hitCount") or 0)
    except (TypeError, ValueError):
        hit_count = 0

    result_list = payload.get("resultList")
    if not isinstance(result_list, dict):
        return [], hit_count
    results = result_list.get("result")
    if not isinstance(results, list):
        return [], hit_count

    out: list[dict[str, str]] = []
    for result in results:
        if not isinstance(result, dict):
            continue

        keyword_parts: list[str] = []
        keyword_list = result.get("keywordList")
        if isinstance(keyword_list, dict):
            kws = keyword_list.get("keyword")
            if isinstance(kws, list):
                keyword_parts.extend(str(k).strip() for k in kws if str(k).strip())

        article = _europepmc_article(
            journal=journal,
            title=str(result.get("title") or "").strip(),
            doi=str(result.get("doi") or "").strip(),
            pmid=str(result.get("pmid") or "").strip(),
            abstract=str(result.get("abstractText") or "").strip(),
            authors=str(result.get("authorString") or "").strip(),
            published=str(result.get("firstPublicationDate") or "").strip(),
            citations_raw=result.get("citedByCount"),
            page_info=str(result.get("pageInfo") or "").strip(),
            keywords=", ".join(keyword_parts),
        )
        if article:
            out.append(article)

    return out, hit_count


def _fetch_europepmc_articles(
    journal: str,
    query: str,
    page_size: int = 50,
    *,
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict[str, str]]:
    """Recent articles from Europe PMC search API with fallback request shapes."""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    request_attempts = [
        ("xml", "core", str(page_size), 45),
        ("json", "core", "20", 30),
        ("xml", "core", "20", 30),
    ]
    errors: list[str] = []

    for fmt, result_type, size, timeout_s in request_attempts:
        accept = "application/xml" if fmt == "xml" else "application/json"
        combined: list[dict[str, str]] = []
        seen: set[str] = set()
        page_size_int = int(size)

        try:
            if fmt == "xml":
                probe_resp = _session().get(
                    url,
                    params={
                        "query": query,
                        "resultType": result_type,
                        "pageSize": size,
                        "format": fmt,
                        "page": "1",
                    },
                    timeout=timeout_s,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": accept,
                    },
                )
                probe_resp.raise_for_status()
                probe_parsed, hit_count = _parse_europepmc_xml(journal, probe_resp.text)
            else:
                probe_resp = _session().get(
                    url,
                    params={
                        "query": query,
                        "resultType": result_type,
                        "pageSize": size,
                        "format": fmt,
                        "page": "1",
                    },
                    timeout=timeout_s,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": accept,
                    },
                )
                probe_resp.raise_for_status()
                try:
                    probe_payload = probe_resp.json()
                except ValueError as e:
                    errors.append(f"json/pageSize={size}/page=1 parse error: {e}")
                    continue
                probe_parsed, hit_count = _parse_europepmc_json(journal, probe_payload)
        except requests.RequestException as e:
            errors.append(f"{fmt}/pageSize={size}/page=1: {e}")
            continue

        start_page = _europepmc_start_page(hit_count, page_size_int, query)
        end_page = min(_EUROPEPMC_MAX_PAGE, start_page + _EUROPEPMC_PAGE_WINDOW - 1)
        pages_to_fetch = list(range(start_page, end_page + 1))

        for page in pages_to_fetch:
            if page == 1:
                parsed = probe_parsed
            else:
                try:
                    if fmt == "xml":
                        page_resp = _session().get(
                            url,
                            params={
                                "query": query,
                                "resultType": result_type,
                                "pageSize": size,
                                "format": fmt,
                                "page": str(page),
                            },
                            timeout=timeout_s,
                            headers={
                                "User-Agent": USER_AGENT,
                                "Accept": accept,
                            },
                        )
                        page_resp.raise_for_status()
                        parsed, _ = _parse_europepmc_xml(journal, page_resp.text)
                    else:
                        page_resp = _session().get(
                            url,
                            params={
                                "query": query,
                                "resultType": result_type,
                                "pageSize": size,
                                "format": fmt,
                                "page": str(page),
                            },
                            timeout=timeout_s,
                            headers={
                                "User-Agent": USER_AGENT,
                                "Accept": accept,
                            },
                        )
                        page_resp.raise_for_status()
                        try:
                            page_payload = page_resp.json()
                        except ValueError as e:
                            errors.append(f"json/pageSize={size}/page={page} parse error: {e}")
                            break
                        parsed, _ = _parse_europepmc_json(journal, page_payload)
                except requests.RequestException as e:
                    errors.append(f"{fmt}/pageSize={size}/page={page}: {e}")
                    break

            if not parsed:
                if page == 1:
                    errors.append(f"{fmt}/pageSize={size}: empty results")
                break

            for article in parsed:
                if not _in_year_range(article, year_min, year_max):
                    continue
                aid = article.get("id", "")
                if aid and aid in seen:
                    continue
                if aid:
                    seen.add(aid)
                combined.append(article)

        if combined:
            return combined

    if errors:
        logger.warning("Europe PMC fetch failed (%s): %s", query, " | ".join(errors))
    return []


def _fetch_feed_xml(url: str) -> str | None:
    try:
        r = _session().get(
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


def fetch_articles_for_source(
    source: dict[str, str],
    *,
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict[str, str]]:
    """Return normalised article dicts for a single entry in the same shape as :func:`fetch_all_articles`."""
    out: list[dict[str, str]] = []
    journal = source["journal"]
    if source.get("europepmc_query"):
        return _fetch_europepmc_articles(
            journal,
            str(source["europepmc_query"]),
            year_min=year_min,
            year_max=year_max,
        )

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

    doi_to_citations: dict[str, int | None] = {}

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

        doi = _entry_doi(entry, link=link, abstract=abstract, title=title)
        citation_count: int | None = None
        if doi:
            if doi not in doi_to_citations:
                doi_to_citations[doi] = _openalex_citation_count_for_doi(doi)
            citation_count = doi_to_citations[doi]
        citations = str(citation_count if citation_count is not None else _UNKNOWN_CITATIONS_DEFAULT)

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
                "page_count": "0",
            }
        )
    return out


def fetch_all_articles(*, year_min: int | None = None, year_max: int | None = None) -> list[dict[str, str]]:
    """Return normalised article dicts from all configured feeds."""
    out: list[dict[str, str]] = []
    for source in SOURCES:
        source_articles = fetch_articles_for_source(source, year_min=year_min, year_max=year_max)
        source_name = str(source.get("journal") or source.get("rss") or source.get("europepmc_query") or "unknown")
        logger.info("Source %-40s -> %s article(s)", source_name[:40], len(source_articles))
        out.extend(source_articles)
    return out
