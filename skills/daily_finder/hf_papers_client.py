from __future__ import annotations

import json
from html import unescape
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.models import CandidateItem
from core.settings import (
    HTTP_RETRY_ATTEMPTS,
    HTTP_RETRY_MAX_WAIT_SECONDS,
    HTTP_RETRY_MIN_WAIT_SECONDS,
    HUGGINGFACE_PAPERS_URL,
)


def _safe_int(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    if cleaned in {"-", ""}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        if cleaned.endswith("k"):
            try:
                return int(float(cleaned[:-1]) * 1000)
            except ValueError:
                return None
    return None


@retry(
    reraise=True,
    stop=stop_after_attempt(HTTP_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=HTTP_RETRY_MIN_WAIT_SECONDS, max=HTTP_RETRY_MAX_WAIT_SECONDS),
    retry=retry_if_exception_type(requests.RequestException),
)
def _fetch_hf_html() -> str:
    response = requests.get(
        HUGGINGFACE_PAPERS_URL,
        headers={"User-Agent": "elena-daily-scout/0.1"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def fetch_huggingface_daily_papers() -> list[CandidateItem]:
    """Fetch daily papers by scraping the public Hugging Face papers page."""
    soup = BeautifulSoup(_fetch_hf_html(), "lxml")
    daily_papers_root = soup.select_one('[data-target="DailyPapers"]')
    if daily_papers_root and daily_papers_root.get("data-props"):
        payload = json.loads(unescape(daily_papers_root["data-props"]))
        daily_papers = payload.get("dailyPapers", [])
        items: list[CandidateItem] = []
        current_date = datetime.now(timezone.utc)
        for entry in daily_papers:
            paper = entry.get("paper", {})
            paper_id = paper.get("id")
            title = (paper.get("title") or "").strip()
            if not paper_id or not title:
                continue
            raw_summary = (paper.get("ai_summary") or paper.get("summary") or "").strip()
            keywords = paper.get("ai_keywords") or []
            items.append(
                CandidateItem(
                    id=f"huggingface:{paper_id}",
                    source="huggingface",
                    title=title,
                    summary=raw_summary or "Hugging Face daily paper",
                    url=urljoin("https://huggingface.co", f"/papers/{paper_id}"),
                    published_at=current_date,
                    tags=["daily-paper", "huggingface", *keywords[:5]],
                    authors=[author.get("name", "") for author in paper.get("authors", []) if author.get("name")],
                    metadata={
                        "community_signal": paper.get("upvotes"),
                        "github_repo": paper.get("githubRepo"),
                    },
                )
            )
        if items:
            return items

    items: list[CandidateItem] = []
    current_date = datetime.now(timezone.utc)
    for heading in soup.select("h3"):
        title_link = heading.select_one("a")
        if not title_link:
            continue

        title = title_link.get_text(" ", strip=True)
        if not title:
            continue

        container = heading.parent
        context_texts: list[str] = []
        for sibling in container.find_all_next(limit=6):
            if sibling.name == "h3":
                break
            text = sibling.get_text(" ", strip=True)
            if text:
                context_texts.append(text)

        social_links = container.select("a")
        reactions = []
        for link in social_links:
            text = link.get_text(" ", strip=True)
            score = _safe_int(text)
            if score is not None:
                reactions.append(score)

        summary = " | ".join(context_texts[:3]) if context_texts else "Hugging Face daily paper"
        items.append(
            CandidateItem(
                id=f"huggingface:{title.lower()}",
                source="huggingface",
                title=title,
                summary=summary,
                url=urljoin("https://huggingface.co", title_link.get("href", "")),
                published_at=current_date,
                tags=["daily-paper", "huggingface"],
                metadata={"community_signal": max(reactions) if reactions else None},
            )
        )
    return items
