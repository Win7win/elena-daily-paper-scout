from __future__ import annotations

import json
from typing import Any

from core.models import EatenPaper
from core.settings import ARCHIVE_PATH


DEFAULT_ARCHIVE = {"papers": []}

PDF_MODE_PRIORITY = {
    "none": 1,
    "basic": 2,
    "mineru": 3,
}


def load_archive() -> dict[str, Any]:
    if not ARCHIVE_PATH.exists():
        ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVE_PATH.write_text(json.dumps(DEFAULT_ARCHIVE, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_ARCHIVE))
    return json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))


def save_archive(archive: dict[str, Any]) -> None:
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_papers(records: list[EatenPaper]) -> None:
    archive = load_archive()
    existing = archive.get("papers", [])
    record_map = {paper["item_id"]: paper for paper in existing}
    for record in records:
        existing_record = record_map.get(record.item_id)
        incoming = record.model_dump(mode="json")
        if not existing_record:
            record_map[record.item_id] = incoming
            continue

        current_priority = PDF_MODE_PRIORITY.get(existing_record.get("pdf_mode", "none"), 0)
        incoming_priority = PDF_MODE_PRIORITY.get(record.pdf_mode, 0)
        if incoming_priority > current_priority:
            record_map[record.item_id] = incoming
            continue
        if incoming_priority == current_priority and incoming.get("created_at", "") >= existing_record.get("created_at", ""):
            record_map[record.item_id] = incoming
    archive["papers"] = sorted(record_map.values(), key=lambda item: item.get("created_at", ""), reverse=True)[:500]
    save_archive(archive)


def search_archive(query: str, limit: int = 10) -> list[dict[str, Any]]:
    archive = load_archive()
    lowered = query.lower().strip()
    if not lowered:
        return archive.get("papers", [])[:limit]
    matches = []
    for paper in archive.get("papers", []):
        haystack = " ".join(
            [
                paper.get("title", ""),
                paper.get("abstract", ""),
                paper.get("technical_summary", ""),
                " ".join(paper.get("focus_topics", [])),
            ]
        ).lower()
        if lowered in haystack:
            matches.append(paper)
    return matches[:limit]
