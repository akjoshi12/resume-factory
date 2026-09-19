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
    pages: int | None = None
    spacing_risk: bool = False
    notes: str = ""


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
