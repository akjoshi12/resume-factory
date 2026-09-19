"""Service-layer test: the path the UI actually calls.

Covers what the graph tests do not -- that applications persist, that the dashboard
row is updated from graph state, and that a paused thread can be re-read after the
process forgets about it (the restart case the checkpointer exists for).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from rfactory import service
from rfactory.config import settings
from rfactory.db.models import Stage

sys.path.insert(0, str(Path(__file__).parent))
from test_graph_smoke import TRACK  # noqa: E402

JD = "Data quality analyst. SQL, Power BI, validation, stakeholder reporting."


def test_application_persists_and_dashboard_row_is_updated(isolated):
    record = service.create_application(track=TRACK, jd_text=JD)
    assert record.thread_id.endswith(record.id)

    gate = service.start(record.id)
    assert gate is not None and gate["kind"] == "resume"

    stored = service.get_application(record.id)
    assert stored.company == "Northwind Health"
    assert stored.role_title == "Data Quality Analyst"
    assert stored.pages == 1
    assert 0 < stored.coverage <= 1
    assert Path(stored.resume_pdf).exists()
    assert service.artifact_path(record.id, "resume") is not None

    assert [a.id for a in service.list_applications()] == [record.id]


def test_paused_thread_is_recoverable_after_the_app_forgets_it(isolated):
    record = service.create_application(track=TRACK, jd_text=JD)
    service.start(record.id)

    # Simulate a restart: drop the compiled graph and rebuild from the checkpoint file.
    service._app = None
    gate = service.pending_gate(record.id)
    assert gate is not None, "a paused review must survive a restart"
    assert gate["kind"] == "resume"
    assert gate["draft"]["professional"], "draft should come back intact"


def test_completing_both_gates_marks_the_application_complete(isolated):
    record = service.create_application(track=TRACK, jd_text=JD)
    service.start(record.id)
    assert service.resume(record.id, {"action": "approve"})["kind"] == "cover"
    assert service.resume(record.id, {"action": "approve"}) is None

    stored = service.get_application(record.id)
    assert stored.stage == Stage.COMPLETE
    assert Path(stored.cover_pdf).exists()


def test_edited_draft_survives_a_revise_round_trip(isolated):
    record = service.create_application(track=TRACK, jd_text=JD)
    gate = service.start(record.id)

    draft = gate["draft"]
    draft["objective"] = "Edited by hand in the review pane."
    after = service.resume(record.id, {"action": "revise", "draft": draft})

    assert after["kind"] == "resume", "revise should return to the same gate"
    assert after["draft"]["objective"] == "Edited by hand in the review pane."
