"""Smoke test: send the daily-summary card to your chat with stub variables.

Reads FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_DAILY_CHAT_ID,
FEISHU_TEMPLATE_DAILY_SUMMARY_ID and FEISHU_TEMPLATE_DAILY_SUMMARY_VERSION
from .env. Run this after importing the daily-summary card template into
your own Feishu app.

Usage:
    python scripts/test_card_send.py
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
    template_id = _required("FEISHU_TEMPLATE_DAILY_SUMMARY_ID")
    template_version = _required("FEISHU_TEMPLATE_DAILY_SUMMARY_VERSION")

    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    now = datetime.now(timezone.utc)
    variables = {
        "date": now.strftime("%Y-%m-%d"),
        "overall_comment": "Smoke test — this is the daily-summary card with stub data.",
        "topics": "deep research / AI scientist / tool use",
        "n_arxiv": 30,
        "n_hf": 12,
        "n_gh": 25,
        "top_k": 5,
        "daily_run_id": now.isoformat(timespec="seconds"),
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
