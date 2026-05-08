from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class CandidateItem(BaseModel):
    """Unified content candidate from different sources."""

    id: str
    source: Literal["arxiv", "github", "huggingface"]
    title: str
    summary: str
    url: HttpUrl
    published_at: datetime
    tags: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | None] = Field(default_factory=dict)


class JudgedItem(BaseModel):
    """A candidate selected for final delivery."""

    item_id: str
    reason: str


class EatenPaper(BaseModel):
    """Archived result of a fast/deep paper eating pass."""

    item_id: str
    mode: Literal["fast", "deep"]
    pdf_mode: Literal["none", "basic", "mineru"]
    source: Literal["arxiv", "huggingface"]
    title: str
    url: HttpUrl
    authors: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    abstract: str
    contribution_guess: str
    framework_guess: str
    result_guess: str
    technical_summary: str
    interesting_bits: list[str] = Field(default_factory=list)
    verdict: str
    grade: Literal["S", "A", "B", "C", "D"]
    relevance_reason: str
    focus_topics: list[str] = Field(default_factory=list)
    created_at: str
    metadata: dict[str, str | int | float | None] = Field(default_factory=dict)


class DailyPaperSummary(BaseModel):
    title: str
    summary: str
    comment: str
    url: HttpUrl
    grade: Literal["S", "A", "B", "C", "D"] | str = "B"


class DailyRepoSummary(BaseModel):
    title: str
    summary: str
    url: HttpUrl


class DailyDigest(BaseModel):
    overall_comment: str
    papers: list[DailyPaperSummary] = Field(default_factory=list)
    hf_papers: list[DailyPaperSummary] = Field(default_factory=list)
    github_repos: list[DailyRepoSummary] = Field(default_factory=list)


class RunState(BaseModel):
    """Persisted state for each daily scout run."""

    last_run_at: str | None = None
    last_status: str | None = None
    latest_message: str | None = None
    latest_selected_ids: list[str] = Field(default_factory=list)
    run_history: list[dict] = Field(default_factory=list)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ChatMemoryNote(BaseModel):
    id: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    created_at: str


class ChatSessionState(BaseModel):
    running_summary: str = ""
    recent_turns: list[ChatTurn] = Field(default_factory=list)
    notes: list[ChatMemoryNote] = Field(default_factory=list)
    last_active_at: str | None = None


class PaperNote(BaseModel):
    id: str
    paper_title: str
    note: str
    grade: Literal["S", "A", "B", "C", "D"] = "B"
    topics: list[str] = Field(default_factory=list)
    item_id: str | None = None
    paper_source: str | None = None
    source_hint: str | None = None
    raw_message: str
    created_at: str
    updated_at: str | None = None
