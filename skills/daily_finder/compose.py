from __future__ import annotations

import json
import re

from core.llm import LLMUnavailableError, chat_completion
from core.models import CandidateItem, DailyDigest, DailyPaperSummary, DailyRepoSummary, EatenPaper
from core.prompts import (
    DIGEST_LABELS,
    compose_digest_system_prompt,
    compose_hf_system_prompt,
    fallback_no_signal,
    fallback_overall,
)


def _brief_intro(paper: EatenPaper, limit: int = 90) -> str:
    source = paper.technical_summary or paper.abstract or paper.contribution_guess
    compact = re.sub(r"\s+", " ", source).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _fallback_digest(topics: list[str], papers: list[EatenPaper]) -> DailyDigest:
    if not papers:
        return DailyDigest(overall_comment=fallback_no_signal(topics), papers=[], hf_papers=[], github_repos=[])

    return DailyDigest(
        overall_comment=fallback_overall(topics),
        papers=[
            DailyPaperSummary(
                title=paper.title,
                summary=_brief_intro(paper),
                comment=paper.verdict,
                url=paper.url,
                grade=paper.grade,
            )
            for paper in papers[:5]
        ],
        hf_papers=[],
        github_repos=[],
    )


def _fallback_hf_papers(hf_items: list[CandidateItem]) -> list[DailyPaperSummary]:
    return [
        DailyPaperSummary(
            title=item.title,
            summary=re.sub(r"\s+", " ", item.summary).strip()[:140],
            comment="",
            url=item.url,
            grade="B",
        )
        for item in hf_items
    ]


def compose_hf_papers(topics: list[str], hf_items: list[CandidateItem]) -> list[DailyPaperSummary]:
    if not hf_items:
        return []

    payload = [
        {
            "title": item.title,
            "summary": item.summary[:500],
            "tags": item.tags,
            "url": str(item.url),
        }
        for item in hf_items
    ]
    user_prompt = (
        f"Current focus: {json.dumps(topics, ensure_ascii=False)}\n"
        f"Hugging Face Daily Papers: {json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = chat_completion(
            system_prompt=compose_hf_system_prompt(),
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=900,
        )
        parsed = json.loads(raw)
        return [DailyPaperSummary(**item) for item in parsed.get("hf_papers", [])]
    except (LLMUnavailableError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return _fallback_hf_papers(hf_items)


def compose_daily_digest(
    topics: list[str],
    papers: list[EatenPaper],
    hf_items: list[CandidateItem],
    github_items: list[CandidateItem],
) -> DailyDigest:
    if not papers and not hf_items and not github_items:
        return DailyDigest(overall_comment=fallback_no_signal(topics), papers=[], hf_papers=[], github_repos=[])

    payload = [
        {
            "grade": paper.grade,
            "title": paper.title,
            "verdict": paper.verdict,
            "technical_summary": paper.technical_summary,
            "abstract": paper.abstract,
            "interesting_bits": paper.interesting_bits,
            "url": str(paper.url),
        }
        for paper in papers[:5]
    ]
    github_payload = [
        {
            "title": item.title,
            "summary": item.summary[:300],
            "url": str(item.url),
        }
        for item in github_items
    ]
    user_prompt = (
        f"Current focus: {json.dumps(topics, ensure_ascii=False)}\n"
        f"arXiv results: {json.dumps(payload, ensure_ascii=False)}\n"
        f"GitHub Trending: {json.dumps(github_payload, ensure_ascii=False)}"
    )
    hf_papers = compose_hf_papers(topics, hf_items)
    try:
        raw = chat_completion(
            system_prompt=compose_digest_system_prompt(),
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=900,
        )
        parsed = json.loads(raw)
        parsed["hf_papers"] = [paper.model_dump(mode="json") for paper in hf_papers]
        return DailyDigest(**parsed)
    except (LLMUnavailableError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return DailyDigest(
            overall_comment=_fallback_digest(topics, papers).overall_comment,
            papers=_fallback_digest(topics, papers).papers,
            hf_papers=hf_papers,
            github_repos=[
                DailyRepoSummary(
                    title=item.title,
                    summary=re.sub(r"\s+", " ", item.summary).strip()[:120],
                    url=item.url,
                )
                for item in github_items
            ],
        )


def render_daily_message(digest: DailyDigest) -> str:
    if not digest.papers and not digest.hf_papers and not digest.github_repos:
        return digest.overall_comment

    label_comment = DIGEST_LABELS["comment"]
    label_summary = DIGEST_LABELS["summary"]
    label_url = DIGEST_LABELS["url"]

    lines = [digest.overall_comment]
    if digest.papers:
        lines.append("")
        lines.append("ArXiv")
        for index, paper in enumerate(digest.papers, start=1):
            lines.append(f"{index}. [{paper.grade}] {paper.title}")
            lines.append(f"{label_comment}: {paper.comment}")
            lines.append(f"{label_summary}: {paper.summary}")
            lines.append(f"{label_url}: {paper.url}")
            lines.append("")
    if digest.hf_papers:
        lines.append("Hugging Face Daily Papers")
        for index, paper in enumerate(digest.hf_papers, start=1):
            lines.append(f"{index}. [{paper.grade}] {paper.title}")
            if paper.comment.strip():
                lines.append(f"{label_comment}: {paper.comment}")
            lines.append(f"{label_summary}: {paper.summary}")
            lines.append(f"{label_url}: {paper.url}")
            lines.append("")
    if digest.github_repos:
        lines.append("GitHub Trending")
        for index, repo in enumerate(digest.github_repos, start=1):
            lines.append(f"{index}. {repo.title}")
            lines.append(f"{label_summary}: {repo.summary}")
            lines.append(f"{label_url}: {repo.url}")
            lines.append("")
    return "\n".join(line for line in lines if line is not None).strip()
