"""Thin layer between the UI and the graph.

Reflex event handlers are async and LangGraph's checkpointed invoke is blocking, so
every entry point here is synchronous and the UI calls it through asyncio.to_thread.
Keeping that boundary in one file stops the two concurrency models from tangling.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any

from langgraph.types import Command
from sqlmodel import select

from rfactory.config import settings
from rfactory.db.models import Application, DraftVersion, Stage
from rfactory.db.session import get_session, init_db
from rfactory.graph.build import compile_graph

logger = logging.getLogger(__name__)

RECURSION_LIMIT = 60

_app = None


def graph():  # type: ignore[no-untyped-def]
    global _app
    if _app is None:
        init_db()
        _app = compile_graph()
    return _app


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


def gate_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    """The value passed to interrupt(), or None when the graph ran to completion."""
    interrupts = result.get("__interrupt__")
    return interrupts[0].value if interrupts else None


# -- applications -------------------------------------------------------------


def create_application(
    *,
    track: str,
    jd_url: str = "",
    jd_text: str = "",
    company: str = "",
    role_title: str = "",
    llm_provider: str = "",
    llm_model: str = "",
) -> Application:
    init_db()
    with get_session() as session:
        record = Application(
            thread_id="",
            track=track,
            jd_url=jd_url or None,
            jd_text=jd_text,
            company=company,
            role_title=role_title,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        record.thread_id = f"app-{record.id}"
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def list_applications() -> list[Application]:
    init_db()
    with get_session() as session:
        return list(session.exec(select(Application).order_by(Application.created_at.desc())))


def get_application(application_id: str) -> Application | None:
    init_db()
    with get_session() as session:
        return session.get(Application, application_id)


def update_application(application_id: str, **fields: Any) -> None:
    with get_session() as session:
        record = session.get(Application, application_id)
        if record is None:
            return
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_at = datetime.now(timezone.utc)
        session.add(record)
        session.commit()


def record_version(
    application_id: str, kind: str, payload: str, *, pages: int | None = None,
    decision: str | None = None, feedback: str | None = None, violations: list[str] | None = None,
) -> None:
    with get_session() as session:
        existing = session.exec(
            select(DraftVersion).where(
                DraftVersion.application_id == application_id, DraftVersion.kind == kind
            )
        ).all()
        session.add(
            DraftVersion(
                application_id=application_id,
                kind=kind,
                version=len(existing) + 1,
                payload=payload,
                pages=pages,
                decision=decision,
                feedback=feedback,
                verify_failures="\n".join(violations or []) or None,
            )
        )
        session.commit()


# -- graph driving ------------------------------------------------------------


def _sync_from_state(application_id: str, state: dict[str, Any]) -> None:
    fields: dict[str, Any] = {}
    for key, column in (
        ("company", "company"), ("role_title", "role_title"), ("jd_text", "jd_text"),
        ("pages", "pages"), ("resume_tex", "resume_tex"),
        ("resume_pdf_path", "resume_pdf"), ("cover_pdf_path", "cover_pdf"),
        ("stage", "stage"),
    ):
        if (value := state.get(key)) not in (None, ""):
            fields[column] = value
    if coverage := state.get("coverage"):
        fields["coverage"] = coverage.get("score")
    if parse := state.get("parse"):
        fields["spacing_risk"] = bool(parse.get("spacing_risk"))
    if fields:
        update_application(application_id, **fields)


def start(application_id: str) -> dict[str, Any] | None:
    record = get_application(application_id)
    if record is None:
        raise ValueError(f"no application {application_id}")
    result = graph().invoke(
        {
            "application_id": record.id,
            "track": record.track,
            "jd_url": record.jd_url or "",
            "jd_text": record.jd_text,
            "company": record.company,
            "role_title": record.role_title,
            "llm_provider": record.llm_provider,
            "llm_model": record.llm_model,
        },
        _config(record.thread_id),
    )
    _sync_from_state(application_id, result)
    return gate_payload(result)


def resume(application_id: str, decision: dict[str, Any]) -> dict[str, Any] | None:
    record = get_application(application_id)
    if record is None:
        raise ValueError(f"no application {application_id}")
    result = graph().invoke(Command(resume=decision), _config(record.thread_id))
    _sync_from_state(application_id, result)
    if result.get("stage") == "complete":
        update_application(application_id, stage=Stage.COMPLETE)
    return gate_payload(result)


def snapshot(application_id: str) -> dict[str, Any]:
    record = get_application(application_id)
    if record is None:
        return {}
    state = graph().get_state(_config(record.thread_id))
    return dict(state.values or {})


def pending_gate(application_id: str) -> dict[str, Any] | None:
    """Re-read the interrupt a paused thread is sitting on, so reopening the page after
    a restart lands back on the same review rather than starting over."""
    record = get_application(application_id)
    if record is None:
        return None
    state = graph().get_state(_config(record.thread_id))
    for task in state.tasks or ():
        for interrupt in getattr(task, "interrupts", ()) or ():
            return interrupt.value
    return None


def artifact_path(application_id: str, kind: str):  # type: ignore[no-untyped-def]
    record = get_application(application_id)
    if record is None:
        return None
    path = record.resume_pdf if kind == "resume" else record.cover_pdf
    if not path:
        candidate = settings.out_dir / application_id / f"{kind}.pdf"
        return candidate if candidate.exists() else None
    from pathlib import Path

    resolved = Path(path)
    return resolved if resolved.exists() else None


def delete_application(application_id: str) -> bool:
    """Remove the application, its draft history, its generated files and its graph
    checkpoints. Everything for one application lives under one id, so a delete that
    misses any of these leaves orphans that reappear as phantom rows or stale PDFs."""
    record = get_application(application_id)
    if record is None:
        return False

    thread_id = record.thread_id
    with get_session() as session:
        for version in session.exec(
            select(DraftVersion).where(DraftVersion.application_id == application_id)
        ).all():
            session.delete(version)
        if (row := session.get(Application, application_id)) is not None:
            session.delete(row)
        session.commit()

    folder = settings.out_dir / application_id
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)

    # The checkpointer keeps its own tables keyed by thread_id; without this the
    # thread lingers and a recycled id would resume someone else's half-finished run.
    try:
        with sqlite3.connect(str(settings.db_path)) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            for table in tables:
                columns = {info[1] for info in connection.execute(f"PRAGMA table_info({table})")}
                if "thread_id" in columns:
                    connection.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            connection.commit()
    except sqlite3.Error:
        logger.warning("could not clear checkpoints for thread %s", thread_id)

    return True
