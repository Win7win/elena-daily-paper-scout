from __future__ import annotations

import base64
import hashlib
import hmac
import time

import requests

from core.settings import FEISHU_BOT_KEYWORD, FEISHU_BOT_SECRET, FEISHU_BOT_WEBHOOK


class FeishuConfigError(RuntimeError):
    """Raised when Feishu bot configuration is incomplete."""


def _build_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _normalize_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return FEISHU_BOT_KEYWORD
    lowered = stripped.lower()
    if FEISHU_BOT_KEYWORD.lower() in lowered:
        return stripped
    return f"【{FEISHU_BOT_KEYWORD}】\n {stripped}"


def send_text_message(text: str) -> dict:
    """Send a signed text message to the configured Feishu bot webhook."""
    if not FEISHU_BOT_WEBHOOK or not FEISHU_BOT_SECRET:
        raise FeishuConfigError("Missing FEISHU_BOT_WEBHOOK or FEISHU_BOT_SECRET")

    timestamp = str(int(time.time()))
    payload = {
        "timestamp": timestamp,
        "sign": _build_sign(timestamp, FEISHU_BOT_SECRET),
        "msg_type": "text",
        "content": {"text": _normalize_text(text)},
    }
    response = requests.post(FEISHU_BOT_WEBHOOK, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()
