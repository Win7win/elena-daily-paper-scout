"""Feishu self-built app integration via lark-oapi long connection.

Two responsibilities:
- Send template-based interactive cards to a chat (used by daily push).
- Run a long-connection listener that dispatches card.action.trigger events
  to a registered handler (used by server.py for feedback callbacks).
"""

from __future__ import annotations

import json
from typing import Callable, Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
)
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)
from lark_oapi.ws import Client as WSClient

from core.settings import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_DAILY_CHAT_ID


class FeishuAppConfigError(RuntimeError):
    pass


def _require_credentials() -> tuple[str, str]:
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        raise FeishuAppConfigError("Missing FEISHU_APP_ID / FEISHU_APP_SECRET")
    return FEISHU_APP_ID, FEISHU_APP_SECRET


def _build_client() -> lark.Client:
    app_id, app_secret = _require_credentials()
    return lark.Client.builder().app_id(app_id).app_secret(app_secret).build()


def send_card_via_template(
    template_id: str,
    template_version: str,
    variables: dict,
    chat_id: Optional[str] = None,
    client: Optional[lark.Client] = None,
) -> str:
    target_chat = chat_id or FEISHU_DAILY_CHAT_ID
    if not target_chat:
        raise FeishuAppConfigError("Missing FEISHU_DAILY_CHAT_ID and no chat_id supplied")
    client = client or _build_client()
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
            .receive_id(target_chat)
            .msg_type("interactive")
            .content(content)
            .build()
        )
        .build()
    )
    response = client.im.v1.message.create(request)
    if not response.success():
        raise RuntimeError(
            f"Feishu card send failed: code={response.code} msg={response.msg} log_id={response.get_log_id()}"
        )
    return response.data.message_id


def send_text_via_app(
    text: str,
    chat_id: Optional[str] = None,
    client: Optional[lark.Client] = None,
) -> str:
    target_chat = chat_id or FEISHU_DAILY_CHAT_ID
    if not target_chat:
        raise FeishuAppConfigError("Missing FEISHU_DAILY_CHAT_ID and no chat_id supplied")
    client = client or _build_client()
    content = json.dumps({"text": text}, ensure_ascii=False)
    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(target_chat)
            .msg_type("text")
            .content(content)
            .build()
        )
        .build()
    )
    response = client.im.v1.message.create(request)
    if not response.success():
        raise RuntimeError(
            f"Feishu text send failed: code={response.code} msg={response.msg} log_id={response.get_log_id()}"
        )
    return response.data.message_id


def patch_card_template(
    message_id: str,
    template_id: str,
    template_version: str,
    variables: dict,
    client: Optional[lark.Client] = None,
) -> None:
    """Update an existing card by re-rendering with new template variables.

    Used by action handlers to disable buttons or change copy after a click.
    """
    client = client or _build_client()
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
        PatchMessageRequest.builder()
        .message_id(message_id)
        .request_body(PatchMessageRequestBody.builder().content(content).build())
        .build()
    )
    response = client.im.v1.message.patch(request)
    if not response.success():
        raise RuntimeError(
            f"Feishu card patch failed: code={response.code} msg={response.msg} log_id={response.get_log_id()}"
        )


CardActionHandler = Callable[[P2CardActionTrigger], P2CardActionTriggerResponse]


def run_card_action_listener(handler: CardActionHandler) -> None:
    """Block forever, dispatching card.action.trigger events to handler.

    Intended to be invoked from a thread or as the foreground process. Returns
    only on KeyboardInterrupt or if the WS client tears down.
    """
    app_id, app_secret = _require_credentials()
    dispatcher = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_card_action_trigger(handler)
        .build()
    )
    ws_client = WSClient(app_id, app_secret, log_level=lark.LogLevel.WARNING, event_handler=dispatcher)
    ws_client.start()
