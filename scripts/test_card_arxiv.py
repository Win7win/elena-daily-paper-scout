"""Smoke test: send the arxiv-papers card with three stub papers.

The card includes the four action buttons (deep_eat / up_vote / normal /
down_vote). Pair this with scripts/listen_card_actions.py to verify that
clicks come back with the right per-paper payload.

Usage:
    python scripts/test_card_arxiv.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        sys.exit(f"{name} missing in .env")
    return value


def main() -> None:
    app_id = _required("FEISHU_APP_ID")
    app_secret = _required("FEISHU_APP_SECRET")
    chat_id = _required("FEISHU_DAILY_CHAT_ID")
    template_id = _required("FEISHU_TEMPLATE_ARXIV_PAPER_ID")
    template_version = _required("FEISHU_TEMPLATE_ARXIV_PAPER_VERSION")

    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    now = datetime.now(timezone.utc)
    daily_run_id = now.isoformat(timespec="seconds")

    variables = {
        "arxiv_list": [
            {
                "idx": 1,
                "grade": "A",
                "title": "Self-Refining Research Agents via Tool-Use Replay",
                "arxiv_url": "https://arxiv.org/abs/2509.04321",
                "verdict": "Topic is on the deep-research-agent main line; relevant; ablations are thin.",
                "technical_summary": "Replays past tool-use traces to fine-tune research agents; rewards final answers, not intermediate steps.",
                "interesting_bits": "Trace-level reward decomposition, closer to RLHF than to step-level credit assignment.",
                "source": "arxiv",
                "published_date": "2026-05-04",
                "primary_category": "cs.CL",
                "arxiv_id": "2509.04321",
                "daily_run_id": daily_run_id,
            },
            {
                "idx": 2,
                "grade": "B",
                "title": "Tool-Aware Planner with Reflective Replanning",
                "arxiv_url": "https://arxiv.org/abs/2509.05012",
                "verdict": "Idea is incremental, but evaluation is careful — usable as a comparison baseline.",
                "technical_summary": "Adds a reflective replanner that rewrites plans based on intermediate execution results.",
                "interesting_bits": "Step-mismatch metric quantifies plan drift, finer-grained than success rate.",
                "source": "arxiv",
                "published_date": "2026-05-03",
                "primary_category": "cs.AI",
                "arxiv_id": "2509.05012",
                "daily_run_id": daily_run_id,
            },
            {
                "idx": 3,
                "grade": "C",
                "title": "Yet Another Long-Context Benchmark for Code Agents",
                "arxiv_url": "https://arxiv.org/abs/2509.05098",
                "verdict": "Topic is fine but setup is too close to existing SWE-bench; no clear independent signal.",
                "technical_summary": "Builds a long-context coding benchmark; evaluates retrieval-aware editing.",
                "interesting_bits": "",
                "source": "arxiv",
                "published_date": "2026-05-02",
                "primary_category": "cs.SE",
                "arxiv_id": "2509.05098",
                "daily_run_id": daily_run_id,
            },
        ],
    }
    content = json.dumps(
        {
            "type": "template",
            "data": {
                "template_id": template_id,
                "template_version_name": template_version,
                "template_variable": variables,
            },
        },
        ensure_ascii=False,
    )

    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(content)
            .build()
        )
        .build()
    )

    response = client.im.v1.message.create(request)
    if response.success():
        print("OK")
        print(f"message_id : {response.data.message_id}")
        return

    print("FAIL")
    print(f"code    : {response.code}")
    print(f"msg     : {response.msg}")
    print(f"log_id  : {response.get_log_id()}")
    sys.exit(1)


if __name__ == "__main__":
    main()
