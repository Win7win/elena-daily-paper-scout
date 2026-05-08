"""Dispatch Feishu card.action.trigger events to feedback / deep-eat handlers."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from lark_oapi.event.callback.model.p2_card_action_trigger import (
    CallBackToast,
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)

from core.feedback import record_feedback
from core.feishu_app import send_text_via_app
from core.memory import load_memory
from core.persona import CARD_ACTION_STRINGS, TOAST_MESSAGES
from skills.arxiv_eater.service import eat_candidates
from skills.daily_finder.arxiv_client import fetch_arxiv_by_id

logger = logging.getLogger(__name__)


def _toast(content: str, type_: str = "info") -> CallBackToast:
    toast = CallBackToast()
    toast.type = type_
    toast.content = content
    return toast


def _spawn_deep_eat(
    *,
    arxiv_id: str,
    title: str | None,
    daily_run_id: str | None,
) -> None:
    def worker() -> None:
        try:
            item = fetch_arxiv_by_id(arxiv_id)
            if item is None:
                send_text_via_app(CARD_ACTION_STRINGS["deep_eat_not_found"].format(arxiv_id=arxiv_id))
                return
            memory = load_memory()
            topics = memory.get("recent_focus", []) or memory.get("long_term_interests", [])
            records = eat_candidates([item], topics, mode="deep", pdf_mode="mineru")
            if not records:
                send_text_via_app(CARD_ACTION_STRINGS["deep_eat_empty"].format(arxiv_id=arxiv_id))
                return
            paper = records[0]
            send_text_via_app(_render_deep_result(paper, daily_run_id))
        except Exception as exc:  # noqa: BLE001
            logger.exception("deep_eat worker failed: %s", exc)
            try:
                send_text_via_app(CARD_ACTION_STRINGS["deep_eat_error"].format(arxiv_id=arxiv_id, exc=exc))
            except Exception:  # noqa: BLE001
                logger.exception("deep_eat error notify failed")

    threading.Thread(target=worker, name=f"deep-eat-{arxiv_id}", daemon=True).start()


def _render_deep_result(paper, daily_run_id: str | None) -> str:
    s = CARD_ACTION_STRINGS
    lines = [s["deep_eat_done_header"].format(grade=paper.grade, title=paper.title)]
    if paper.url:
        lines.append(f"{s['label_url']}: {paper.url}")
    if paper.verdict:
        lines.append(f"{s['label_verdict']}: {paper.verdict}")
    if paper.technical_summary:
        lines.append(f"{s['label_technical']}: {paper.technical_summary}")
    if paper.contribution_guess:
        lines.append(f"{s['label_contribution']}: {paper.contribution_guess}")
    if paper.framework_guess:
        lines.append(f"{s['label_framework']}: {paper.framework_guess}")
    if paper.result_guess:
        lines.append(f"{s['label_result']}: {paper.result_guess}")
    if paper.interesting_bits:
        lines.append(f"{s['label_interesting']}:")
        for bit in paper.interesting_bits:
            lines.append(f"  · {bit}")
    if daily_run_id:
        lines.append(f"{s['label_run_id']}: {daily_run_id}")
    return "\n".join(lines)


def handle_card_action(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    event = data.event
    action = event.action if event else None
    operator = event.operator if event else None
    value = (action.value or {}) if action else {}

    name = str(value.get("action") or "")
    arxiv_id = str(value.get("arxiv_id") or "") or None
    title = str(value.get("title") or "") or None
    grade = str(value.get("grade") or "") or None
    daily_run_id = str(value.get("daily_run_id") or "") or None
    user_open_id = operator.open_id if operator else None

    response = P2CardActionTriggerResponse()

    if name == "deep_eat":
        if arxiv_id:
            _spawn_deep_eat(arxiv_id=arxiv_id, title=title, daily_run_id=daily_run_id)
            response.toast = _toast(TOAST_MESSAGES.get(name, "ok"))
        else:
            response.toast = _toast(CARD_ACTION_STRINGS["missing_arxiv_id"], type_="error")
    elif name in {"up_vote", "normal", "down_vote"}:
        record_feedback(
            action=name,
            arxiv_id=arxiv_id,
            title=title,
            grade=grade,
            daily_run_id=daily_run_id,
            user_open_id=user_open_id,
        )
        response.toast = _toast(TOAST_MESSAGES.get(name, "noted"))
    else:
        logger.warning("unknown card action: name=%r value=%r", name, value)
        response.toast = _toast(CARD_ACTION_STRINGS["unknown_action"].format(name=name), type_="error")

    return response
