"""Deleting an application must not leave orphans.

Everything for one application is keyed by its id or its thread id: the row, its draft
history, its PDFs on disk, and the checkpointer's own tables. A delete that misses any
of them shows up later as a phantom row or a resumable thread for a deleted job.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from rfactory import service
from rfactory.config import settings

sys.path.insert(0, str(Path(__file__).parent))
from test_graph_smoke import TRACK  # noqa: E402


def _threads_in_checkpointer() -> set[str]:
    found: set[str] = set()
    with sqlite3.connect(str(settings.db_path)) as connection:
        for (table,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall():
            columns = {info[1] for info in connection.execute(f"PRAGMA table_info({table})")}
            if "thread_id" in columns:
                found |= {row[0] for row in connection.execute(f"SELECT DISTINCT thread_id FROM {table}")}
    return found


def test_delete_removes_row_files_and_checkpoints(isolated):
    record = service.create_application(track=TRACK, jd_text="SQL and Power BI.")
    service.start(record.id)

    stored = service.get_application(record.id)
    pdf = Path(stored.resume_pdf)
    assert pdf.exists()
    assert record.thread_id in _threads_in_checkpointer()

    assert service.delete_application(record.id) is True

    assert service.get_application(record.id) is None
    assert [a.id for a in service.list_applications()] == []
    assert not pdf.parent.exists(), "generated PDFs should go with the application"
    assert record.thread_id not in _threads_in_checkpointer(), "checkpoint thread lingered"


def test_deleting_one_leaves_the_others_intact(isolated):
    first = service.create_application(track=TRACK, jd_text="SQL.")
    second = service.create_application(track=TRACK, jd_text="Power BI.")
    service.start(first.id)
    service.start(second.id)

    service.delete_application(first.id)

    assert [a.id for a in service.list_applications()] == [second.id]
    assert Path(service.get_application(second.id).resume_pdf).exists()
    assert second.thread_id in _threads_in_checkpointer()


def test_deleting_something_that_is_not_there_is_not_an_error(isolated):
    assert service.delete_application("nope") is False


def test_the_model_used_is_recorded_on_the_application(isolated):
    record = service.create_application(
        track=TRACK, jd_text="SQL.", llm_provider="gateway", llm_model="deepseek/deepseek-chat"
    )
    stored = service.get_application(record.id)
    assert stored.llm_provider == "gateway"
    assert stored.llm_model == "deepseek/deepseek-chat"
