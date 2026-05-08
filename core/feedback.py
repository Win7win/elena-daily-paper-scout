"""Feedback storage for daily card actions.

Two layers:

- ``feedback.jsonl`` (append-only, full history) — audit trail of every click.
- ``feedback_latest.json`` (dict keyed by arxiv_id) — current evaluation per
  paper. The latest click for an arxiv_id overwrites the previous entry. Used
  by the ranker for taste calibration.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from core.settings import DATA_DIR

FEEDBACK_PATH = DATA_DIR / "feedback.jsonl"
FEEDBACK_LATEST_PATH = DATA_DIR / "feedback_latest.json"

_LOCK = threading.Lock()


def _load_latest_unlocked() -> dict[str, dict]:
    if not FEEDBACK_LATEST_PATH.exists():
        return {}
    try:
        return json.loads(FEEDBACK_LATEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_latest_unlocked(latest: dict[str, dict]) -> None:
    FEEDBACK_LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_LATEST_PATH.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")


def record_feedback(
    *,
    action: str,
    arxiv_id: str | None,
    title: str | None,
    grade: str | None,
    daily_run_id: str | None,
    user_open_id: str | None,
    extra: dict | None = None,
) -> dict:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action,
        "arxiv_id": arxiv_id,
        "title": title,
        "grade": grade,
        "daily_run_id": daily_run_id,
        "user_open_id": user_open_id,
    }
    if extra:
        entry["extra"] = extra

    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    with _LOCK:
        with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if arxiv_id:
            latest = _load_latest_unlocked()
            latest[arxiv_id] = entry
            _save_latest_unlocked(latest)
    return entry


def load_feedback() -> list[dict]:
    if not FEEDBACK_PATH.exists():
        return []
    entries: list[dict] = []
    for line in FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_latest_feedback() -> dict[str, dict]:
    """Return current evaluation per arxiv_id (latest click wins)."""
    with _LOCK:
        return _load_latest_unlocked()


def get_latest_for(arxiv_id: str) -> dict | None:
    return load_latest_feedback().get(arxiv_id)
