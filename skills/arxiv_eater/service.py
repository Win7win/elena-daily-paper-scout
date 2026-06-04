from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime, timedelta, timezone

from core.archive import upsert_papers
from core.llm import LLMUnavailableError, chat_completion
from core.models import CandidateItem, EatenPaper
from core.prompts import (
    SERVICE_FALLBACKS,
    eater_analyze_system_prompt,
    eater_rank_system_prompt,
)
from core.settings import ARXIV_CATEGORIES, DAILY_PAPER_FETCH_LIMIT, DAILY_PAPER_TOP_K
from skills.arxiv_eater.config import load_eater_config
from skills.arxiv_eater.pdf_ops import cleanup_temp_files, download_pdf, extract_text_with_pdfplumber, parse_pdf_with_mineru
from skills.arxiv_eater.section_extract import extract_signal_sections
from skills.daily_finder.arxiv_client import fetch_recent_rss, search_arxiv


def build_arxiv_query(topics: list[str]) -> str:
    """Build an arXiv official API query using category filters plus all-fields topic phrases."""
    category_query = " OR ".join(f"cat:{category}" for category in ARXIV_CATEGORIES)
    topic_terms = " OR ".join(f'all:"{topic}"' for topic in topics if topic.strip())
    if topic_terms:
        return f"({category_query}) AND ({topic_terms})"
    return category_query


def _dedup_by_id(items: list[CandidateItem]) -> list[CandidateItem]:
    seen: set[str] = set()
    out: list[CandidateItem] = []
    for item in sorted(items, key=lambda it: it.published_at, reverse=True):
        if item.id in seen:
            continue
        seen.add(item.id)
        out.append(item)
    return out


def _topic_keyword_filter(topics: list[str], items: list[CandidateItem]) -> list[CandidateItem]:
    phrases = [t.lower() for t in topics if t.strip()]
    if not phrases:
        return items
    tokens = {tok for phrase in phrases for tok in phrase.split() if len(tok) >= 4}
    matched: list[CandidateItem] = []
    for item in items:
        hay = f"{item.title} {item.summary}".lower()
        if any(p in hay for p in phrases) or any(tok in hay for tok in tokens):
            matched.append(item)
    return matched


def search_topic_papers(topics: list[str], days_back: int, max_results: int = DAILY_PAPER_FETCH_LIMIT) -> list[CandidateItem]:
    normalized_topics = [topic.strip() for topic in topics if topic.strip()]
    primary: list[CandidateItem] = []
    try:
        primary = search_arxiv(
            query=build_arxiv_query(normalized_topics),
            max_results=max_results,
            days_back=days_back,
        )
    except Exception:
        primary = []
    if primary:
        return _dedup_by_id(primary)

    rss_items = fetch_recent_rss(ARXIV_CATEGORIES)
    if days_back is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        rss_items = [it for it in rss_items if it.published_at >= cutoff]
    filtered = _topic_keyword_filter(normalized_topics, rss_items)
    pool = filtered if filtered else rss_items
    return _dedup_by_id(pool)[:max_results]


def _fallback_rank(topics: list[str], candidates: list[CandidateItem], top_k: int) -> list[CandidateItem]:
    normalized = [topic.lower() for topic in topics if topic.strip()]
    scored: list[tuple[int, CandidateItem]] = []
    for item in candidates:
        haystack = f"{item.title} {item.summary} {' '.join(item.tags)}".lower()
        score = sum(3 for topic in normalized if topic in haystack)
        score += sum(1 for topic in normalized for token in topic.split() if len(token) >= 4 and token in haystack)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
    return [item for _, item in scored[:top_k]]


def rank_candidates_for_focus(topics: list[str], candidates: list[CandidateItem], top_k: int = DAILY_PAPER_TOP_K) -> list[CandidateItem]:
    """Do a cheap relevance pass before detailed eating."""
    if not candidates:
        return []
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "summary": item.summary[:1000],
            "tags": item.tags,
            "authors": item.authors[:5],
        }
        for item in candidates
    ]
    user_prompt = (
        f"Current focus: {json.dumps(topics, ensure_ascii=False)}\n"
        f"Candidates: {json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = chat_completion(
            system_prompt=eater_rank_system_prompt(),
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=500,
        )
        selected_ids = json.loads(raw).get("selected_ids", [])[:top_k]
        selected_map = {item.id: item for item in candidates}
        selected = [selected_map[item_id] for item_id in selected_ids if item_id in selected_map]
        if selected:
            return selected
    except (LLMUnavailableError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return _fallback_rank(topics, candidates, top_k)


def exclude_recently_seen(memory: dict, candidates: list[CandidateItem]) -> list[CandidateItem]:
    recent_ids = set(memory.get("recently_sent_ids", []))
    recent_titles = {title.lower().strip() for title in memory.get("recently_sent_titles", [])}
    return [
        item
        for item in candidates
        if item.id not in recent_ids and item.title.lower().strip() not in recent_titles
    ]


def _fallback_analysis(item: CandidateItem, topics: list[str], sections: dict[str, str], mode: str) -> EatenPaper:
    title_text = item.title.lower()
    summary_text = item.summary.lower()
    focus_hits = [topic for topic in topics if topic.lower() in f"{title_text} {summary_text}"]
    grade = "C" if focus_hits else "D"
    if any(term in title_text for term in ["agent", "retrieval", "eval", "judge", "coding"]) and focus_hits:
        grade = "B"
    if any(term in title_text for term in ["benchmark", "deepresearch", "persona", "simulation"]) and len(focus_hits) >= 2:
        grade = "A"
    return EatenPaper(
        item_id=item.id,
        mode=mode,
        pdf_mode="none",
        source=item.source,
        title=item.title,
        url=item.url,
        authors=item.authors,
        institutions=[],
        abstract=item.summary,
        contribution_guess=sections["contribution"][:300] or item.summary[:300],
        framework_guess=sections["framework"][:300] or SERVICE_FALLBACKS["framework_missing"],
        result_guess=sections["results"][:300] or SERVICE_FALLBACKS["results_missing"],
        technical_summary=item.summary[:300],
        interesting_bits=focus_hits[:3] or [SERVICE_FALLBACKS["weak_signal"]],
        verdict=SERVICE_FALLBACKS["parkable"],
        grade=grade,
        relevance_reason=SERVICE_FALLBACKS["topic_overlap"] if focus_hits else SERVICE_FALLBACKS["weak_relevance"],
        focus_topics=topics,
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata=item.metadata,
    )


def _llm_analyze(item: CandidateItem, topics: list[str], sections: dict[str, str], mode: str) -> EatenPaper:
    payload = {
        "topics": topics,
        "title": item.title,
        "authors": item.authors,
        "abstract": item.summary,
        "contribution_section": sections["contribution"][:3000],
        "framework_section": sections["framework"][:3000],
        "results_section": sections["results"][:3000],
    }
    max_tokens = 1200 if mode == "deep" else 700
    raw = chat_completion(
        system_prompt=eater_analyze_system_prompt(mode),
        user_prompt=json.dumps(payload, ensure_ascii=False),
        temperature=0.2,
        max_tokens=max_tokens,
    )
    parsed = json.loads(raw)
    return EatenPaper(
        item_id=item.id,
        mode=mode,
        pdf_mode="none",
        source=item.source,
        title=item.title,
        url=item.url,
        authors=item.authors,
        institutions=[],
        abstract=item.summary,
        contribution_guess=parsed["contribution_guess"],
        framework_guess=parsed["framework_guess"],
        result_guess=parsed["result_guess"],
        technical_summary=parsed["technical_summary"],
        interesting_bits=parsed["interesting_bits"],
        verdict=parsed["verdict"],
        grade=parsed["grade"],
        relevance_reason=parsed["relevance_reason"],
        focus_topics=topics,
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata=item.metadata,
    )


def _grade_rank_value(grade: str) -> int:
    return {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}.get(grade, 0)


def _downgrade_grade(grade: str) -> str:
    return {"S": "A", "A": "B", "B": "C", "C": "D", "D": "D"}.get(grade, "C")


def calibrate_grades(records: list[EatenPaper]) -> list[EatenPaper]:
    """Make grades more discriminative within one batch."""
    if not records:
        return records

    sorted_records = sorted(records, key=lambda paper: _grade_rank_value(paper.grade), reverse=True)
    calibrated: list[EatenPaper] = []
    s_used = 0
    a_used = 0
    for index, paper in enumerate(sorted_records):
        grade = paper.grade
        if grade == "S":
            if s_used >= 1:
                grade = "A"
            else:
                s_used += 1
        if grade == "A":
            if a_used >= 2:
                grade = "B"
            else:
                a_used += 1
        if index >= 3 and grade in {"A", "S"}:
            grade = _downgrade_grade(grade)
        if index >= 5 and grade in {"B", "A", "S"}:
            grade = _downgrade_grade(grade)
        if grade != paper.grade:
            calibrated.append(paper.model_copy(update={"grade": grade}))
        else:
            calibrated.append(paper)
    return sorted(calibrated, key=lambda paper: _grade_rank_value(paper.grade), reverse=True)


def eat_candidates(
    candidates: list[CandidateItem],
    topics: list[str],
    mode: str = "fast",
    pdf_mode: str = "basic",
) -> list[EatenPaper]:
    """Run fast/deep analysis on selected candidates and archive the results."""
    config = load_eater_config()
    max_workers = max(1, int(config.get("analysis_max_workers", 4)))

    def process_item(item: CandidateItem) -> EatenPaper:
        paper_id = item.id.rsplit("/", maxsplit=1)[-1].replace(":", "_").replace(".", "_")
        markdown = ""
        pdf_url = item.metadata.get("pdf_url") if item.metadata else None
        try:
            if pdf_url:
                pdf_path = download_pdf(str(pdf_url), paper_id)
                if pdf_path:
                    if pdf_mode == "mineru":
                        parse_method = "auto" if mode == "deep" else "txt"
                        markdown = parse_pdf_with_mineru(pdf_path, paper_id, method=parse_method) or ""
                    elif pdf_mode == "basic":
                        markdown = extract_text_with_pdfplumber(pdf_path)
        except Exception:
            markdown = ""
        finally:
            cleanup_temp_files(paper_id)

        sections = extract_signal_sections(markdown) if markdown else {"contribution": "", "framework": "", "results": ""}
        try:
            record = _llm_analyze(item, topics, sections, mode)
        except (LLMUnavailableError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            record = _fallback_analysis(item, topics, sections, mode)
        return record.model_copy(update={"pdf_mode": pdf_mode})

    records: list[EatenPaper] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(candidates) or 1)) as executor:
        futures = [executor.submit(process_item, item) for item in candidates]
        for future in as_completed(futures):
            records.append(future.result())
    records = calibrate_grades(records)
    upsert_papers(records)
    return sorted(records, key=lambda paper: _grade_rank_value(paper.grade), reverse=True)
