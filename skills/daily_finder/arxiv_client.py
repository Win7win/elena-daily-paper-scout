from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import time
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.models import CandidateItem
from core.settings import (
    ARXIV_CATEGORIES,
    ARXIV_DAYS_BACK,
    ARXIV_MAX_RESULTS,
    HTTP_RETRY_ATTEMPTS,
    HTTP_RETRY_MAX_WAIT_SECONDS,
    HTTP_RETRY_MIN_WAIT_SECONDS,
)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_USER_AGENT = "elena-daily-paper-scout/0.1 (+https://github.com/Win7win/elena-daily-paper-scout)"
ARXIV_MIN_INTERVAL_SECONDS = 3.5  # arXiv API guideline: keep ≥3s between requests.
ARXIV_RATE_LIMIT_BACKOFF_CAP_SECONDS = 300.0

_arxiv_last_call_ts = 0.0


class ArxivRateLimited(Exception):
    """arXiv responded with 429/503 (rate-limit or throttled)."""

    def __init__(self, retry_after: float):
        super().__init__(f"arxiv rate limited; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


def _respect_min_interval() -> None:
    global _arxiv_last_call_ts
    elapsed = time.monotonic() - _arxiv_last_call_ts
    if elapsed < ARXIV_MIN_INTERVAL_SECONDS:
        time.sleep(ARXIV_MIN_INTERVAL_SECONDS - elapsed)


def _mark_called() -> None:
    global _arxiv_last_call_ts
    _arxiv_last_call_ts = time.monotonic()


@retry(
    reraise=True,
    stop=stop_after_attempt(HTTP_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=HTTP_RETRY_MIN_WAIT_SECONDS, max=HTTP_RETRY_MAX_WAIT_SECONDS),
    retry=retry_if_exception_type(requests.RequestException),
)
def _get_arxiv_feed_once(url: str) -> str:
    _respect_min_interval()
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": ARXIV_USER_AGENT})
    finally:
        _mark_called()
    if response.status_code in (429, 503):
        retry_after_hdr = response.headers.get("Retry-After")
        try:
            retry_after = float(retry_after_hdr) if retry_after_hdr else 60.0
        except (TypeError, ValueError):
            retry_after = 60.0
        raise ArxivRateLimited(min(retry_after, ARXIV_RATE_LIMIT_BACKOFF_CAP_SECONDS))
    response.raise_for_status()
    return response.text


def _get_arxiv_feed(url: str) -> str:
    return _get_arxiv_feed_once(url)


def _build_item(entry: feedparser.FeedParserDict) -> CandidateItem:
    tags = [tag.term for tag in entry.get("tags", [])]
    authors = [author.name for author in entry.get("authors", [])]
    links = entry.get("links", [])
    pdf_url = None
    for link in links:
        if link.get("type") == "application/pdf":
            pdf_url = link.get("href")
            break
    return CandidateItem(
        id=entry.id,
        source="arxiv",
        title=" ".join(entry.title.split()),
        summary=" ".join(entry.summary.split()),
        url=entry.link,
        published_at=datetime(*entry.published_parsed[:6], tzinfo=timezone.utc),
        tags=tags,
        authors=authors,
        metadata={
            "primary_category": tags[0] if tags else None,
            "pdf_url": pdf_url,
        },
    )


def extract_arxiv_id(text: str) -> str | None:
    patterns = [
        r"arxiv\.org/abs/([0-9]+\.[0-9]+(?:v[0-9]+)?)",
        r"arxiv\.org/pdf/([0-9]+\.[0-9]+(?:v[0-9]+)?)",
        r"\b([0-9]+\.[0-9]+(?:v[0-9]+)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _patient_get_arxiv_feed(url: str, attempts: int = 2) -> str:
    """Like _get_arxiv_feed but waits out a rate-limit once (for background single-item fetches)."""
    last_exc: Exception | None = None
    for index in range(attempts):
        try:
            return _get_arxiv_feed_once(url)
        except ArxivRateLimited as exc:
            last_exc = exc
            if index < attempts - 1:
                time.sleep(exc.retry_after)
    raise last_exc  # type: ignore[misc]


def _fetch_arxiv_by_id_from_abs(arxiv_id: str) -> CandidateItem | None:
    """Fallback when the export API is throttled: scrape the abs page (not rate-limited like the API)."""
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    _respect_min_interval()
    try:
        resp = requests.get(abs_url, timeout=30, headers={"User-Agent": ARXIV_USER_AGENT})
    except requests.RequestException:
        return None
    finally:
        _mark_called()
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    def _meta(name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name})
        content = tag.get("content") if tag else None
        return content or None

    title = " ".join((_meta("citation_title") or "").split())
    if not title:
        return None
    pdf_url = _meta("citation_pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}"
    blockquote = soup.find("blockquote", class_="abstract")
    summary = blockquote.get_text(" ", strip=True) if blockquote else ""
    summary = " ".join(re.sub(r"^Abstract:\s*", "", summary).split())
    authors = [m.get("content", "") for m in soup.find_all("meta", attrs={"name": "citation_author"})]
    authors = [a for a in authors if a]
    primary_category = _meta("citation_arxiv_category")

    published_at = datetime.now(timezone.utc)
    date_str = _meta("citation_date") or _meta("citation_online_date")
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        if not date_str:
            break
        try:
            published_at = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue

    return CandidateItem(
        id=f"http://arxiv.org/abs/{arxiv_id}",
        source="arxiv",
        title=title,
        summary=summary,
        url=abs_url,
        published_at=published_at,
        tags=[primary_category] if primary_category else [],
        authors=authors,
        metadata={"primary_category": primary_category, "pdf_url": pdf_url},
    )


def fetch_arxiv_by_id(arxiv_id: str) -> CandidateItem | None:
    clean = arxiv_id.strip()
    url = f"{ARXIV_API_URL}?id_list={quote_plus(clean)}"
    try:
        feed = feedparser.parse(_patient_get_arxiv_feed(url))
        if feed.entries:
            return _build_item(feed.entries[0])
    except (ArxivRateLimited, requests.RequestException):
        pass
    return _fetch_arxiv_by_id_from_abs(clean)


def fetch_recent_arxiv() -> list[CandidateItem]:
    """Fetch recent papers from the official arXiv API."""
    category_query = " OR ".join(f"cat:{category}" for category in ARXIV_CATEGORIES)
    return search_arxiv(query=category_query, max_results=ARXIV_MAX_RESULTS, days_back=ARXIV_DAYS_BACK)


_RSS_ID_RE = re.compile(r"(\d{4}\.\d{4,5}v\d+)")
_RSS_ABSTRACT_PREFIX_RE = re.compile(r"^arXiv:\S+\s+Announce Type:.*?Abstract:\s*", flags=re.S)


def _extract_versioned_arxiv_id(entry) -> str | None:
    raw_id = entry.get("id", "") or ""
    m = _RSS_ID_RE.search(raw_id)
    if m:
        return m.group(1)
    link = entry.get("link", "") or ""
    m = re.search(r"abs/(\d{4}\.\d{4,5}v\d+)", link)
    return m.group(1) if m else None


def _build_item_from_rss(entry, primary_category: str) -> CandidateItem | None:
    arxiv_id = _extract_versioned_arxiv_id(entry)
    if not arxiv_id:
        return None
    norm_id = f"http://arxiv.org/abs/{arxiv_id}"
    link = entry.get("link") or f"https://arxiv.org/abs/{arxiv_id.split('v')[0]}"
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    raw_summary = entry.get("summary", "") or ""
    cleaned_summary = _RSS_ABSTRACT_PREFIX_RE.sub("", raw_summary)
    summary = " ".join(cleaned_summary.split())
    title = " ".join((entry.get("title") or "").split())
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    published_at = datetime(*pub[:6], tzinfo=timezone.utc) if pub else datetime.now(timezone.utc)
    tag_terms = [t.get("term") if isinstance(t, dict) else getattr(t, "term", None) for t in entry.get("tags", [])]
    tags = [t for t in tag_terms if t] or [primary_category]
    authors: list[str] = []
    for author in entry.get("authors", []) or []:
        name = author.get("name") if isinstance(author, dict) else getattr(author, "name", "")
        if not name:
            continue
        if "," in name:
            authors.extend(piece.strip() for piece in name.split(",") if piece.strip())
        else:
            authors.append(name)
    return CandidateItem(
        id=norm_id,
        source="arxiv",
        title=title,
        summary=summary,
        url=link,
        published_at=published_at,
        tags=tags,
        authors=authors,
        metadata={"primary_category": primary_category, "pdf_url": pdf_url},
    )


def fetch_recent_rss(categories: list[str]) -> list[CandidateItem]:
    """Fetch newest entries per category via arXiv's RSS feed (no search-query throttle)."""
    items: list[CandidateItem] = []
    seen_ids: set[str] = set()
    for category in categories:
        url = f"https://export.arxiv.org/rss/{category}"
        try:
            body = _get_arxiv_feed(url)
        except Exception:
            continue
        feed = feedparser.parse(body)
        for entry in feed.entries:
            item = _build_item_from_rss(entry, primary_category=category)
            if item is None or item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            items.append(item)
    items.sort(key=lambda it: it.published_at, reverse=True)
    return items


def search_arxiv(query: str, max_results: int = ARXIV_MAX_RESULTS, days_back: int | None = ARXIV_DAYS_BACK) -> list[CandidateItem]:
    """Search arXiv with the official API and normalize into CandidateItem."""
    url = (
        f"{ARXIV_API_URL}?search_query={quote_plus(query)}"
        f"&sortBy=submittedDate&sortOrder=descending&start=0&max_results={max_results}"
    )
    feed = feedparser.parse(_get_arxiv_feed(url))

    cutoff = None
    if days_back is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    items: list[CandidateItem] = []
    for entry in feed.entries:
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if cutoff is not None and published < cutoff:
            continue
        items.append(_build_item(entry))
    return items
