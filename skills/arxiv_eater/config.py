from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().with_name("config.json")

DEFAULT_CONFIG = {
    "search_fetch_limit": 100,
    "ranking_batch_size": 20,
    "ranking_batch_pick": 5,
    "fast_top_k": 12,
    "fast_pdf_mode": "basic",
    "deep_top_k": 4,
    "deep_pdf_mode": "basic",
    "analysis_max_workers": 4,
    "feishu_push_default": False,
}


def load_eater_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(DEFAULT_CONFIG)
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged
