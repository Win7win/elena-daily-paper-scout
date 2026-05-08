"""Build Feishu template variable dicts from daily pipeline results."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from core.models import CandidateItem, DailyDigest, EatenPaper
from skills.daily_finder.arxiv_client import extract_arxiv_id


def _topics_to_string(topics: list[str]) -> str:
    return " / ".join(topic.strip() for topic in topics if topic and topic.strip())


def _strip_arxiv_version(arxiv_id: str | None) -> str:
    if not arxiv_id:
        return ""
    return re.sub(r"v\d+$", "", arxiv_id)


def build_summary_variables(
    *,
    digest: DailyDigest,
    topics: list[str],
    n_arxiv: int,
    n_hf: int,
    n_gh: int,
    top_k: int,
    daily_run_id: str,
    run_date_utc: datetime | None = None,
) -> dict:
    run_date_utc = run_date_utc or datetime.now(timezone.utc)
    return {
        "date": run_date_utc.strftime("%Y-%m-%d"),
        "overall_comment": digest.overall_comment,
        "topics": _topics_to_string(topics),
        "n_arxiv": int(n_arxiv),
        "n_hf": int(n_hf),
        "n_gh": int(n_gh),
        "top_k": int(top_k),
        "daily_run_id": daily_run_id,
    }


def _build_arxiv_paper_item(paper: EatenPaper, idx: int, daily_run_id: str) -> dict:
    arxiv_id_norm = _strip_arxiv_version(extract_arxiv_id(paper.item_id) or extract_arxiv_id(str(paper.url)) or paper.item_id)
    interesting = " · ".join(paper.interesting_bits) if paper.interesting_bits else ""
    technical = paper.technical_summary or paper.contribution_guess or paper.abstract
    primary_category = ""
    published_date = ""
    if isinstance(paper.metadata, dict):
        primary_category = str(paper.metadata.get("primary_category") or "")
        published_date = str(paper.metadata.get("published_date") or "")
    return {
        "idx": int(idx),
        "grade": paper.grade,
        "title": paper.title,
        "arxiv_url": str(paper.url),
        "verdict": paper.verdict,
        "technical_summary": technical,
        "interesting_bits": interesting,
        "source": paper.source,
        "published_date": published_date,
        "primary_category": primary_category,
        "arxiv_id": arxiv_id_norm,
        "daily_run_id": daily_run_id,
    }


def build_arxiv_papers_variables(
    *,
    papers: list[EatenPaper],
    daily_run_id: str,
) -> dict:
    return {
        "arxiv_list": [
            _build_arxiv_paper_item(paper, idx, daily_run_id)
            for idx, paper in enumerate(papers, start=1)
        ],
    }


def build_hf_variables(hf_papers) -> dict:
    """Accepts either DailyPaperSummary list or CandidateItem list."""
    items = []
    for entry in hf_papers:
        if isinstance(entry, CandidateItem):
            items.append(
                {
                    "grade": "B",
                    "title": entry.title,
                    "summary": _compact(entry.summary, 160),
                    "url": str(entry.url),
                }
            )
        else:
            items.append(
                {
                    "grade": getattr(entry, "grade", "B") or "B",
                    "title": entry.title,
                    "summary": _compact(getattr(entry, "summary", ""), 160),
                    "url": str(entry.url),
                }
            )
    return {"hf_list": items}


def build_gh_variables(github_repos) -> dict:
    items = []
    for entry in github_repos:
        items.append(
            {
                "title": entry.title,
                "summary": _compact(getattr(entry, "summary", ""), 140),
                "url": str(entry.url),
            }
        )
    return {"gh_list": items}


def _compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
