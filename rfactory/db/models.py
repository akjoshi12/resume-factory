from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class Stage(StrEnum):
    NEW = "new"
    RESUME_REVIEW = "resume_review"
    COVER_REVIEW = "cover_review"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class Outcome(StrEnum):
    """What happened after you sent it. Set by hand from the dashboard."""

    NOT_SENT = "not_sent"
    APPLIED = "applied"
    SCREEN = "screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    WITHDRAWN = "withdrawn"


class Application(SQLModel, table=True):
    id: str = Field(default_factory=_uid, primary_key=True)
    thread_id: str = Field(index=True)  # LangGraph checkpoint thread
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    company: str = ""
    role_title: str = ""
    track: str = ""
    jd_url: str | None = None
    jd_text: str = ""

    stage: str = Stage.NEW
    outcome: str = Outcome.NOT_SENT

    # Which model produced this, so a good or bad result is attributable.
    llm_provider: str = ""
    llm_model: str = ""

    resume_tex: str | None = None
    resume_pdf: str | None = None
    cover_tex: str | None = None
    cover_pdf: str | None = None

    coverage: float | None = None
    ats_score: int | None = None
    pages: int | None = None
    spacing_risk: bool = False
    notes: str = ""

    # Set once, when the resume is approved: the moment it counts as sent.
    applied_at: datetime | None = None
    referral: bool = False

    # Notion mirror (rfactory/sync/notion_sync.py). Bookkeeping, plus the fields Notion owns.
    notion_page_id: str | None = None
    notion_synced_at: datetime | None = None
    next_action: str = ""
    next_action_date: str | None = None


class NotionOutbox(SQLModel, table=True):
    """A Notion push that failed and is waiting to be retried. One row per application."""

    id: int | None = Field(default=None, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    attempts: int = 0
    next_try_at: datetime = Field(default_factory=_now)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=_now)


class DraftVersion(SQLModel, table=True):
    """Every generated or edited draft, so a rejection history is inspectable rather
    than overwritten. payload is a serialised ResumeDraft or CoverLetterDraft."""

    id: int | None = Field(default=None, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    kind: str = "resume"  # "resume" | "cover"
    version: int = 1
    created_at: datetime = Field(default_factory=_now)

    payload: str = ""
    pages: int | None = None
    decision: str | None = None  # "approved" | "rejected" | None
    feedback: str | None = None
    verify_failures: str | None = None
