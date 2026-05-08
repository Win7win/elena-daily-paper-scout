from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from urllib.parse import quote_plus

import feedparser
import requests
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

ARXIV_API_URL = "http://export.arxiv.org/api/query"


@retry(
    reraise=True,
    stop=stop_after_attempt(HTTP_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=HTTP_RETRY_MIN_WAIT_SECONDS, max=HTTP_RETRY_MAX_WAIT_SECONDS),
    retry=retry_if_exception_type(requests.RequestException),
)
def _get_arxiv_feed(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


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


def fetch_arxiv_by_id(arxiv_id: str) -> CandidateItem | None:
    url = f"{ARXIV_API_URL}?id_list={quote_plus(arxiv_id.strip())}"
    feed = feedparser.parse(_get_arxiv_feed(url))
    if not feed.entries:
        return None
    return _build_item(feed.entries[0])


def fetch_recent_arxiv() -> list[CandidateItem]:
    """Fetch recent papers from the official arXiv API."""
    category_query = " OR ".join(f"cat:{category}" for category in ARXIV_CATEGORIES)
    return search_arxiv(query=category_query, max_results=ARXIV_MAX_RESULTS, days_back=ARXIV_DAYS_BACK)


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
