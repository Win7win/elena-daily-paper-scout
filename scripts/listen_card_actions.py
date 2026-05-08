"""Listen for Feishu card.action.trigger events and echo each click.

Usage:
    python scripts/listen_card_actions.py

After it prints "Listening...", click any button on a card the bot has sent.
Each click prints the action payload and replies with a toast so you can see
the click is acknowledged in Feishu.

Stop with Ctrl-C.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    CallBackToast,
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)
from lark_oapi.ws import Client as WSClient


def _load_credentials() -> tuple[str, str]:
    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        sys.exit("FEISHU_APP_ID / FEISHU_APP_SECRET missing in .env")
    return app_id, app_secret


def _handle(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    event = data.event
    timestamp = datetime.now().isoformat(timespec="seconds")
    operator = event.operator if event else None
    action = event.action if event else None
    context = event.context if event else None

    print("==== card.action.trigger ====", flush=True)
    print(f"ts        : {timestamp}", flush=True)
    print(f"operator  : open_id={operator.open_id if operator else None}", flush=True)
    print(
        f"context   : message_id={context.open_message_id if context else None} "
        f"chat_id={context.open_chat_id if context else None}",
        flush=True,
    )
    if action is not None:
        print(f"tag       : {action.tag}", flush=True)
        print(f"name      : {action.name}", flush=True)
        print(f"value     : {json.dumps(action.value, ensure_ascii=False)}", flush=True)
    print("=============================\n", flush=True)

    label = "?"
    if action and action.value:
        label = action.value.get("action") or "?"
    toast = CallBackToast()
    toast.type = "info"
    toast.content = f"received {label} (echo)"
    response = P2CardActionTriggerResponse()
    response.toast = toast
    return response


def main() -> None:
    app_id, app_secret = _load_credentials()
    dispatcher = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_card_action_trigger(_handle)
        .build()
    )
    client = WSClient(app_id, app_secret, log_level=lark.LogLevel.WARNING, event_handler=dispatcher)
    print("Listening for card.action.trigger. Click a button on a card; Ctrl-C to stop.", flush=True)
    client.start()


if __name__ == "__main__":
    main()
