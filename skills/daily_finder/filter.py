from __future__ import annotations

import re

from core.models import CandidateItem
from core.settings import MAX_CANDIDATES_AFTER_FILTER

STOPWORDS = {
    "large",
    "models",
    "model",
    "language",
    "research",
    "practical",
    "workflow",
    "tools",
    "tool",
    "paper",
    "github",
    "products",
}


def _tokenize_keywords(memory: dict) -> list[str]:
    raw_keywords = memory.get("long_term_interests", []) + memory.get("recent_focus", [])
    tokens: list[str] = []
    for phrase in raw_keywords:
        lowered = phrase.lower().strip()
        if not lowered:
            continue
        tokens.append(lowered)
        tokens.extend(
            part
            for part in re.split(r"[^a-z0-9#+.-]+", lowered)
            if len(part) >= 4 and part not in STOPWORDS
        )
    return list(dict.fromkeys(tokens))


def filter_candidates(memory: dict, items: list[CandidateItem]) -> list[CandidateItem]:
    """High-precision coarse filter using simple keyword overlap and de-duplication."""
    keywords = _tokenize_keywords(memory)
    recent_ids = set(memory.get("recently_sent_ids", []))
    recent_titles = {title.lower().strip() for title in memory.get("recently_sent_titles", [])}
    seen_titles: set[str] = set()
    scored: list[tuple[int, CandidateItem]] = []

    for item in items:
        normalized_title = item.title.lower().strip()
        if item.id in recent_ids or normalized_title in recent_titles or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        title_text = item.title.lower()
        summary_text = item.summary.lower()
        tags_text = " ".join(item.tags).lower()
        exact_phrase_hits = sum(1 for keyword in keywords if " " in keyword and keyword in f"{title_text} {summary_text} {tags_text}")
        keyword_hits = sum(1 for keyword in keywords if " " not in keyword and keyword in f"{title_text} {summary_text} {tags_text}")
        if exact_phrase_hits == 0 and keyword_hits < 2:
            continue
        score = exact_phrase_hits * 6 + keyword_hits * 2
        score += sum(2 for keyword in keywords if keyword in title_text)
        score += sum(1 for keyword in keywords if keyword in tags_text)
        if item.source == "arxiv":
            score += 1
        if item.source == "huggingface":
            score += 2
        scored.append((score, item))

    scored.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
    return [item for _, item in scored[:MAX_CANDIDATES_AFTER_FILTER]]
