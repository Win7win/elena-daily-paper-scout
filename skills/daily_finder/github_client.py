from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.models import CandidateItem
from core.settings import (
    GITHUB_TRENDING_URL,
    HTTP_RETRY_ATTEMPTS,
    HTTP_RETRY_MAX_WAIT_SECONDS,
    HTTP_RETRY_MIN_WAIT_SECONDS,
)


@retry(
    reraise=True,
    stop=stop_after_attempt(HTTP_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=HTTP_RETRY_MIN_WAIT_SECONDS, max=HTTP_RETRY_MAX_WAIT_SECONDS),
    retry=retry_if_exception_type(requests.RequestException),
)
def _fetch_github_html() -> str:
    response = requests.get(
        GITHUB_TRENDING_URL,
        headers={"User-Agent": "elena-daily-scout/0.1"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def fetch_github_trending() -> list[CandidateItem]:
    """Fetch GitHub Trending by scraping the public page.

    GitHub does not provide an official Trending API, so v0.1 uses page scraping.
    """
    soup = BeautifulSoup(_fetch_github_html(), "lxml")
    now = datetime.now(timezone.utc)

    items: list[CandidateItem] = []
    for article in soup.select("article.Box-row"):
        title_node = article.select_one("h2 a")
        if not title_node:
            continue
        repo_name = " ".join(title_node.get_text(" ", strip=True).split()).replace(" / ", "/")
        repo_path = title_node.get("href", "").strip()
        description_node = article.select_one("p")
        language_node = article.select_one('[itemprop="programmingLanguage"]')
        star_nodes = article.select("a.Link--muted")
        stars = None
        if star_nodes:
            stars = star_nodes[0].get_text(strip=True)
        summary_parts = []
        if description_node:
            summary_parts.append(description_node.get_text(" ", strip=True))
        if language_node:
            summary_parts.append(f"Language: {language_node.get_text(strip=True)}")
        if stars:
            summary_parts.append(f"Stars: {stars}")
        items.append(
            CandidateItem(
                id=f"github:{repo_name}",
                source="github",
                title=repo_name,
                summary=" | ".join(summary_parts) if summary_parts else "GitHub trending repository",
                url=urljoin("https://github.com", repo_path),
                published_at=now,
                tags=[language_node.get_text(strip=True)] if language_node else [],
                metadata={"stars": stars},
            )
        )
    return items
