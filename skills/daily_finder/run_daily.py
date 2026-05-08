from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from core.feishu import FeishuConfigError, send_text_message
from core.feishu_app import FeishuAppConfigError, send_card_via_template
from core.memory import load_memory, load_state, save_memory, save_state
from core.models import CandidateItem
from core.settings import (
    FEISHU_TEMPLATE_ARXIV_PAPER,
    FEISHU_TEMPLATE_DAILY_SUMMARY,
    FEISHU_TEMPLATE_GH_TRENDING,
    FEISHU_TEMPLATE_HF_PAPERS,
)
from skills.arxiv_eater.service import eat_candidates, exclude_recently_seen, rank_candidates_for_focus, search_topic_papers
from skills.daily_finder.cards import (
    build_arxiv_papers_variables,
    build_gh_variables,
    build_hf_variables,
    build_summary_variables,
)
from skills.daily_finder.compose import compose_daily_digest, render_daily_message
from skills.daily_finder.config import load_daily_config
from skills.daily_finder.github_client import fetch_github_trending
from skills.daily_finder.hf_papers_client import fetch_huggingface_daily_papers

console = Console()


def get_cached_daily_for_today() -> dict | None:
    state = load_state()
    last_run_at = state.get("last_run_at")
    latest_message = state.get("latest_message")
    if not last_run_at or not latest_message:
        return None
    try:
        last_run = datetime.fromisoformat(last_run_at)
    except ValueError:
        return None
    if last_run.astimezone(timezone.utc).date() != datetime.now(timezone.utc).date():
        return None
    return {
        "started_at": last_run_at,
        "message": latest_message,
        "selected_ids": state.get("latest_selected_ids", []),
        "status": state.get("last_status", "ok"),
    }


def _render_papers(title: str, papers: list) -> None:
    config = load_daily_config()
    top_k = int(config["daily_send_top_k"])
    table = Table(title=title)
    table.add_column("Grade")
    table.add_column("Source")
    table.add_column("Title")
    table.add_column("Reason")
    for paper in papers[:top_k]:
        table.add_row(getattr(paper, "grade", "-"), getattr(paper, "source", "-"), paper.title[:64], paper.verdict[:64])
    console.print(table)


def _push_daily_cards(
    *,
    topics: list[str],
    eaten,
    hf_ranked,
    github_items,
    digest,
    n_arxiv: int,
    n_hf: int,
    n_gh: int,
    top_k: int,
    daily_run_id: str,
) -> list[str]:
    summary_id, summary_ver = FEISHU_TEMPLATE_DAILY_SUMMARY
    arxiv_id, arxiv_ver = FEISHU_TEMPLATE_ARXIV_PAPER
    hf_id, hf_ver = FEISHU_TEMPLATE_HF_PAPERS
    gh_id, gh_ver = FEISHU_TEMPLATE_GH_TRENDING

    message_ids: list[str] = []
    summary_vars = build_summary_variables(
        digest=digest,
        topics=topics,
        n_arxiv=n_arxiv,
        n_hf=n_hf,
        n_gh=n_gh,
        top_k=top_k,
        daily_run_id=daily_run_id,
    )
    message_ids.append(send_card_via_template(summary_id, summary_ver, summary_vars))

    if eaten[:top_k]:
        arxiv_vars = build_arxiv_papers_variables(papers=eaten[:top_k], daily_run_id=daily_run_id)
        message_ids.append(send_card_via_template(arxiv_id, arxiv_ver, arxiv_vars))

    if hf_ranked or digest.hf_papers:
        hf_vars = build_hf_variables(digest.hf_papers or hf_ranked)
        message_ids.append(send_card_via_template(hf_id, hf_ver, hf_vars))

    if github_items or digest.github_repos:
        gh_vars = build_gh_variables(digest.github_repos or github_items)
        message_ids.append(send_card_via_template(gh_id, gh_ver, gh_vars))

    return message_ids


def run_daily_pipeline(
    topics_override: list[str] | None = None,
    push_to_feishu: bool = True,
) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    memory = load_memory()
    state = load_state()
    config = load_daily_config()
    topics = topics_override or config.get("active_topics", []) or memory.get("recent_focus", [])
    arxiv_days_back = int(config["arxiv_days_back"])
    arxiv_fetch_limit = int(config["arxiv_fetch_limit"])
    candidate_top_k = int(config["candidate_top_k"])
    basic_pdf_top_k = int(config["basic_pdf_top_k"])
    daily_send_top_k = int(config["daily_send_top_k"])
    hf_relevant_top_k = int(config["hf_relevant_top_k"])
    github_trending_top_k = int(config["github_trending_top_k"])

    fetch_errors: list[str] = []
    arxiv_candidates: list[CandidateItem] = []
    hf_candidates: list[CandidateItem] = []
    github_candidates: list[CandidateItem] = []

    try:
        arxiv_items = search_topic_papers(topics, days_back=arxiv_days_back, max_results=arxiv_fetch_limit)
        arxiv_candidates.extend(arxiv_items)
    except Exception as exc:  # noqa: BLE001
        fetch_errors.append(f"arXiv fetch failed: {exc}")

    try:
        hf_items = fetch_huggingface_daily_papers()
        hf_candidates.extend(hf_items)
    except Exception as exc:  # noqa: BLE001
        fetch_errors.append(f"Hugging Face fetch failed: {exc}")

    try:
        github_items = fetch_github_trending()
        github_candidates.extend(github_items[:github_trending_top_k])
    except Exception as exc:  # noqa: BLE001
        fetch_errors.append(f"GitHub fetch failed: {exc}")

    fresh_arxiv = exclude_recently_seen(memory, arxiv_candidates)
    ranked = rank_candidates_for_focus(topics, fresh_arxiv, top_k=candidate_top_k)
    basic_ranked = ranked[:basic_pdf_top_k]
    abstract_only_ranked = ranked[basic_pdf_top_k:daily_send_top_k]
    eaten_basic = eat_candidates(basic_ranked, topics, mode="fast", pdf_mode="basic") if basic_ranked else []
    eaten_abstract = eat_candidates(abstract_only_ranked, topics, mode="fast", pdf_mode="none") if abstract_only_ranked else []
    eaten = (eaten_basic + eaten_abstract)[:daily_send_top_k]
    fresh_hf = exclude_recently_seen(memory, hf_candidates)
    hf_ranked = rank_candidates_for_focus(topics, fresh_hf, top_k=hf_relevant_top_k)
    digest = compose_daily_digest(topics, eaten[:daily_send_top_k], hf_ranked[:hf_relevant_top_k], github_candidates[:github_trending_top_k])
    message = render_daily_message(digest)

    feishu_status = None
    feishu_response = None
    feishu_mode = None
    if push_to_feishu:
        try:
            feishu_response = _push_daily_cards(
                topics=topics,
                eaten=eaten[:daily_send_top_k],
                hf_ranked=hf_ranked[:hf_relevant_top_k],
                github_items=github_candidates[:github_trending_top_k],
                digest=digest,
                n_arxiv=len(arxiv_candidates),
                n_hf=len(hf_candidates),
                n_gh=len(github_candidates),
                top_k=daily_send_top_k,
                daily_run_id=started_at,
            )
            feishu_status = "sent"
            feishu_mode = "card"
        except FeishuAppConfigError:
            try:
                feishu_response = send_text_message(message)
                feishu_status = "sent"
                feishu_mode = "text_fallback"
            except FeishuConfigError:
                feishu_status = "skipped"
                feishu_mode = "skipped"
            except Exception as exc:  # noqa: BLE001
                feishu_status = f"failed: {exc}"
                feishu_mode = "text_fallback"
        except Exception as exc:  # noqa: BLE001
            feishu_status = f"failed: {exc}"
            feishu_mode = "card"
    else:
        feishu_status = "skipped"
        feishu_mode = "skipped"

    state["last_run_at"] = started_at
    state["last_status"] = "ok" if (arxiv_candidates or hf_candidates or github_candidates) else "degraded"
    state["latest_message"] = message
    state["latest_selected_ids"] = [paper.item_id for paper in eaten[:daily_send_top_k]]
    state.setdefault("run_history", []).append(
        {
            "run_at": started_at,
            "status": state["last_status"],
            "focus_topics": topics,
            "selected_ids": state["latest_selected_ids"],
            "fetch_errors": fetch_errors,
            "feishu_status": feishu_status,
            "feishu_mode": feishu_mode,
            "daily_config": config,
        }
    )
    if eaten:
        memory["recently_sent_ids"] = [paper.item_id for paper in eaten[:daily_send_top_k]] + memory.get("recently_sent_ids", [])
        memory["recently_sent_titles"] = [paper.title for paper in eaten[:daily_send_top_k]] + memory.get("recently_sent_titles", [])
    save_state(state)
    save_memory(memory)

    return {
        "started_at": started_at,
        "topics": topics,
        "config": config,
        "fetch_errors": fetch_errors,
        "arxiv_candidates": arxiv_candidates,
        "hf_candidates": hf_candidates,
        "github_candidates": github_candidates,
        "ranked": ranked,
        "eaten": eaten,
        "hf_ranked": hf_ranked[:hf_relevant_top_k],
        "digest": digest,
        "message": message,
        "feishu_status": feishu_status,
        "feishu_mode": feishu_mode,
        "feishu_response": feishu_response,
    }


def main() -> int:
    result = run_daily_pipeline(push_to_feishu=True)
    config = result["config"]
    topics = result["topics"]
    console.print("[bold cyan]Elena daily papers[/bold cyan]")
    console.print(f"Focus topics: {', '.join(topics) if topics else '(none)'}")
    console.print(
        f"Config: arxiv_days_back={config['arxiv_days_back']}, arxiv_fetch_limit={config['arxiv_fetch_limit']}, "
        f"candidate_top_k={config['candidate_top_k']}, basic_pdf_top_k={config['basic_pdf_top_k']}, "
        f"daily_send_top_k={config['daily_send_top_k']}, hf_relevant_top_k={config['hf_relevant_top_k']}, "
        f"github_trending_top_k={config['github_trending_top_k']}"
    )
    console.print(f"Fetched {len(result['arxiv_candidates'])} arXiv papers.")
    console.print(f"Fetched {len(result['hf_candidates'])} Hugging Face papers.")
    console.print(f"Fetched {len(result['github_candidates'])} GitHub Trending repos.")
    for error in result["fetch_errors"]:
        console.print(f"[red]{error}[/red]")
    if result["eaten"]:
        _render_papers("Daily Top Papers", result["eaten"])

    console.print("\n[bold]Elena message[/bold]")
    console.print(result["message"])
    if result["feishu_status"] == "sent":
        console.print(f"[green]Feishu push sent ({result.get('feishu_mode')}).[/green]")
        console.print(str(result["feishu_response"]))
    elif str(result["feishu_status"]).startswith("failed:"):
        console.print(f"[red]Feishu push failed ({result.get('feishu_mode')}): {result['feishu_status']}[/red]")
    return 0 if (result["arxiv_candidates"] or result["hf_candidates"] or result["github_candidates"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
