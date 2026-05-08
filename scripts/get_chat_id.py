"""One-shot helper: open a Feishu long connection, wait for one message, print
its chat_id, exit.

Usage:
    python scripts/get_chat_id.py

Requires FEISHU_APP_ID and FEISHU_APP_SECRET in your .env (loaded via
python-dotenv) or in the current process environment.

After it prints "Listening...", send any message to your bot in Feishu;
the script will print the originating chat_id and quit.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi.ws import Client as WSClient


def _load_credentials() -> tuple[str, str]:
    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        sys.exit("FEISHU_APP_ID / FEISHU_APP_SECRET missing in .env")
    return app_id, app_secret


def main() -> None:
    app_id, app_secret = _load_credentials()
    captured = threading.Event()

    def handler(data: P2ImMessageReceiveV1) -> None:
        if captured.is_set():
            return
        event = data.event
        if event is None or event.message is None:
            return
        message = event.message
        sender = event.sender
        sender_id = sender.sender_id.open_id if sender and sender.sender_id else "?"
        print("---- captured ----")
        print(f"chat_id    : {message.chat_id}")
        print(f"chat_type  : {message.chat_type}")
        print(f"open_id    : {sender_id}")
        print(f"message_id : {message.message_id}")
        print("------------------")
        sys.stdout.flush()
        captured.set()
        os._exit(0)

    dispatcher = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(handler)
        .build()
    )
    client = WSClient(app_id, app_secret, log_level=lark.LogLevel.WARNING, event_handler=dispatcher)
    print("Listening. Send any message to your bot in Feishu...", flush=True)
    client.start()


if __name__ == "__main__":
    main()
