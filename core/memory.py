from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.persona import USER_NAME
from core.settings import MEMORY_PATH, RECENTLY_SENT_WINDOW, STATE_PATH


# Edit this default profile to seed your own interests on first run.
# After the first run, edit ``data/memory.json`` directly instead.
DEFAULT_MEMORY = {
    "user_profile": {"name": USER_NAME},
    "long_term_interests": [
        "large language models",
        "agents",
        "retrieval",
        "evaluation",
        "developer tools",
    ],
    "recent_focus": [
        "coding agents",
        "paper triage",
        "research workflow",
    ],
    "recently_sent_ids": [],
    "recently_sent_titles": [],
    "focus_history": [],
}

DEFAULT_STATE = {
    "last_run_at": None,
    "last_status": None,
    "latest_message": None,
    "latest_selected_ids": [],
    "run_history": [],
    "scheduler": {
        "last_scheduled_utc_date": None,
        "last_scheduled_run_at": None,
    },
}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    _ensure_parent(path)
    if not path.exists():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.loads(json.dumps(default))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_memory() -> dict[str, Any]:
    return _load_json(MEMORY_PATH, DEFAULT_MEMORY)


def save_memory(memory: dict[str, Any]) -> None:
    dedup_titles = list(dict.fromkeys(memory.get("recently_sent_titles", [])))[:RECENTLY_SENT_WINDOW]
    dedup_ids = list(dict.fromkeys(memory.get("recently_sent_ids", [])))[:RECENTLY_SENT_WINDOW]
    memory["recently_sent_titles"] = dedup_titles
    memory["recently_sent_ids"] = dedup_ids
    _save_json(MEMORY_PATH, memory)


def update_recent_focus(topics: list[str]) -> dict[str, Any]:
    memory = load_memory()
    normalized = [topic.strip() for topic in topics if topic.strip()]
    memory["recent_focus"] = normalized
    history = memory.get("focus_history", [])
    history.append({"updated_at": datetime.now(timezone.utc).isoformat(), "topics": normalized})
    memory["focus_history"] = history[-20:]
    save_memory(memory)
    return memory


def load_state() -> dict[str, Any]:
    return _load_json(STATE_PATH, DEFAULT_STATE)


def save_state(state: dict[str, Any]) -> None:
    history = state.get("run_history", [])
    state["run_history"] = history[-20:]
    _save_json(STATE_PATH, state)
