from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().with_name("config.json")

DEFAULT_CONFIG = {
    "active_topics": [
        "coding agents",
        "terminal tools",
        "paper triage"
    ],
    "arxiv_days_back": 7,
    "arxiv_fetch_limit": 30,
    "candidate_top_k": 5,
    "basic_pdf_top_k": 5,
    "daily_send_top_k": 5,
    "hf_relevant_top_k": 10,
    "github_trending_top_k": 3,
}


def load_daily_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(DEFAULT_CONFIG)
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_daily_config(config: dict[str, Any]) -> None:
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def update_active_topics(topics: list[str]) -> dict[str, Any]:
    config = load_daily_config()
    config["active_topics"] = [topic.strip() for topic in topics if topic.strip()]
    save_daily_config(config)
    return config
