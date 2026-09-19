from __future__ import annotations

from typing import Annotated, Any, TypedDict


class GraphState(TypedDict, total=False):
    """Serialised through the SQLite checkpointer, so everything here is JSON-safe:
    pydantic models are carried as model_dump() dicts, never as instances."""

    application_id: str
    track: str
    llm_provider: str
    llm_model: str

    jd_url: str
    jd_text: str
    company: str
    role_title: str
    requirements: list[str]

    tailoring: dict[str, Any]
    draft: dict[str, Any]

    violations: list[str]
    notes: list[str]
    verify_attempts: int
    fit_attempts: int
    trim_log: list[str]

    resume_tex: str
    resume_pdf_path: str
    pages: int
    coverage: dict[str, Any]
    parse: dict[str, Any]

    resume_feedback: str
    cover_feedback: str
    resume_decision: str
    cover_decision: str
    artifacts: dict[str, Any]

    cover: dict[str, Any]
    cover_pdf_path: str

    stage: str
    errors: list[str]


def append(state: GraphState, key: str, value: Any) -> list[Any]:
    existing = list(state.get(key) or [])
    existing.append(value)
    return existing


__all__ = ["GraphState", "append", "Annotated"]
