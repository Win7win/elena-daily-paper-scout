from __future__ import annotations

import json

import requests

from core.llm import LLMUnavailableError, chat_completion
from core.models import CandidateItem, JudgedItem
from core.prompts import judge_system_prompt, judge_user_prompt
from core.settings import MAX_FINAL_SEND_COUNT

GENERIC_TERMS = {
    "large",
    "language",
    "models",
    "model",
    "llm",
    "research",
    "paper",
    "workflow",
    "practical",
    "products",
    "github",
    "tools",
    "tool",
}

STRONG_TITLE_TERMS = {
    "agent",
    "agents",
    "retrieval",
    "rag",
    "evaluation",
    "judge",
    "coding",
    "developer",
    "terminal",
    "scout",
}


def _normalize_tokens(values: list[str]) -> tuple[list[str], list[str]]:
    phrases = []
    keywords = []
    for phrase in values:
        normalized = phrase.lower().strip()
        if not normalized:
            continue
        phrases.append(normalized)
        for token in normalized.replace("-", " ").split():
            token = token.strip()
            if len(token) >= 4 and token not in GENERIC_TERMS:
                keywords.append(token)
    return list(dict.fromkeys(phrases)), list(dict.fromkeys(keywords))


def _fallback_judge(memory: dict, candidates: list[CandidateItem]) -> list[JudgedItem]:
    recent_phrases, recent_keywords = _normalize_tokens(memory.get("recent_focus", []))
    long_phrases, long_keywords = _normalize_tokens(memory.get("long_term_interests", []))
    selected: list[JudgedItem] = []
    for item in candidates:
        title_text = item.title.lower()
        summary_text = item.summary.lower()
        tags_text = " ".join(item.tags).lower()
        combined = f"{title_text} {summary_text} {tags_text}"

        recent_phrase_hits = [phrase for phrase in recent_phrases if phrase in combined]
        long_phrase_hits = [phrase for phrase in long_phrases if phrase in combined]
        keyword_hits = [keyword for keyword in recent_keywords + long_keywords if keyword in combined]
        title_term_hits = [term for term in STRONG_TITLE_TERMS if term in title_text]

        score = len(recent_phrase_hits) * 5
        score += len(long_phrase_hits) * 2
        score += len(keyword_hits)
        score += len(title_term_hits) * 2
        if score < 6:
            continue
        if not recent_phrase_hits and len(title_term_hits) < 2:
            continue

        reasons = []
        if recent_phrase_hits:
            reasons.append(f"matches your current focus on {recent_phrase_hits[0]}")
        if title_term_hits:
            reasons.append("the title itself carries a strong signal")
        selected.append(
            JudgedItem(
                item_id=item.id,
                reason="; ".join(reasons) if reasons else "overlaps your current interests well above noise.",
            )
        )
        if len(selected) >= MAX_FINAL_SEND_COUNT:
            break
    return selected


def judge_candidates(memory: dict, candidates: list[CandidateItem]) -> list[JudgedItem]:
    """Use LLM for high-precision selection, with heuristic fallback when unavailable."""
    if not candidates:
        return []

    serialized = [
        {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "summary": item.summary[:500],
            "url": str(item.url),
            "published_at": item.published_at.isoformat(),
            "tags": item.tags,
        }
        for item in candidates
    ]
    system_prompt = judge_system_prompt()
    user_prompt = judge_user_prompt(
        long_term_interests=memory.get("long_term_interests", []),
        recent_focus=memory.get("recent_focus", []),
        candidates_serialized=json.dumps(serialized, ensure_ascii=False, indent=2),
    )
    try:
        raw = chat_completion(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1, max_tokens=500)
        parsed = json.loads(raw)
        selected = parsed.get("selected", [])[:MAX_FINAL_SEND_COUNT]
        return [JudgedItem(**item) for item in selected]
    except (LLMUnavailableError, requests.RequestException, json.JSONDecodeError, ValueError, KeyError, TypeError, NameError):
        return _fallback_judge(memory, candidates)
