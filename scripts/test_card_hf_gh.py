"""Smoke test: send the HF papers card and the GitHub trending card with stub data.

Usage:
    python scripts/test_card_hf_gh.py
"""

from __future__ import annotations

import json
import os
import sys
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


def _send(client: lark.Client, chat_id: str, template: tuple[str, str], variables: dict) -> None:
    template_id, version = template
    content = json.dumps(
        {
            "type": "template",
            "data": {
                "template_id": template_id,
                "template_version_name": version,
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
    if not response.success():
        print(
            f"FAIL template={template_id} code={response.code} "
            f"msg={response.msg} log_id={response.get_log_id()}"
        )
        sys.exit(1)
    print(f"OK template={template_id} message_id={response.data.message_id}")


def main() -> None:
    app_id = _required("FEISHU_APP_ID")
    app_secret = _required("FEISHU_APP_SECRET")
    chat_id = _required("FEISHU_DAILY_CHAT_ID")
    hf_template = (
        _required("FEISHU_TEMPLATE_HF_PAPERS_ID"),
        _required("FEISHU_TEMPLATE_HF_PAPERS_VERSION"),
    )
    gh_template = (
        _required("FEISHU_TEMPLATE_GH_TRENDING_ID"),
        _required("FEISHU_TEMPLATE_GH_TRENDING_VERSION"),
    )

    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    hf_variables = {
        "hf_list": [
            {
                "grade": "A",
                "title": "Tool-Use Replay for Self-Refining Agents",
                "summary": "Trace replay used as self-reflection signal; relevant to deep-research-agent line.",
                "url": "https://huggingface.co/papers/2509.04321",
            },
            {
                "grade": "B",
                "title": "Sparse Mixture-of-Experts at 1B Scale",
                "summary": "Pushes MoE sparsity into smaller models; engineering-heavy, insight-light.",
                "url": "https://huggingface.co/papers/2509.05012",
            },
            {
                "grade": "C",
                "title": "Yet Another Long-Context Benchmark",
                "summary": "Construction is close to existing benchmarks; nothing standout.",
                "url": "https://huggingface.co/papers/2509.05098",
            },
        ],
    }
    gh_variables = {
        "gh_list": [
            {
                "title": "anthropics/claude-agent-sdk",
                "summary": "Anthropic's agent SDK; supports custom tools and long-session orchestration.",
                "url": "https://github.com/anthropics/claude-agent-sdk",
            },
            {
                "title": "huggingface/smolagents",
                "summary": "Lightweight agent framework focused on minimum-code tool-use agents.",
                "url": "https://github.com/huggingface/smolagents",
            },
            {
                "title": "openai/codex",
                "summary": "OpenAI's local coding-agent CLI; recent updates around exec mode.",
                "url": "https://github.com/openai/codex",
            },
        ],
    }

    _send(client, chat_id, hf_template, hf_variables)
    _send(client, chat_id, gh_template, gh_variables)


if __name__ == "__main__":
    main()
