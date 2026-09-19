"""End-to-end graph test with a stub model.

Exercises the wiring that is expensive to debug later: both interrupt gates, resume
after interrupt, the deterministic trim loop, claim verification, and real LaTeX
compilation. No LM Studio required -- the provider is stubbed, so this runs in CI.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from rfactory.config import settings
from rfactory.graph import build
from rfactory.llm.provider import CallStats
from rfactory.graph.nodes import cover as cover_nodes
from rfactory.graph.nodes import ingest as ingest_nodes
from rfactory.graph.nodes import tailor as tailor_nodes
from rfactory.models.master import MasterResume

TRACK = "data_analyst"  # three roles plus Paragon: the track that overflows one page


class StubProvider:
    """Returns schema-appropriate JSON, wrapped in the <think> block and code fence a
    local reasoning model actually emits, so the extraction path is exercised too."""

    name = "stub"

    def __init__(self, fabricate: bool = False, rewrite: bool = False):
        self.fabricate = fabricate
        self.rewrite = rewrite
        self.calls: list[str] = []
        self.last = CallStats()

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        schema: dict | None = None,
        schema_name: str = "response",
    ) -> str:
        master = MasterResume.load(settings.master_resume)
        if "Extract the company" in user:
            self.calls.append("ingest")
            payload = {
                "company": "Northwind Health",
                "role_title": "Data Quality Analyst",
                "requirements": ["SQL", "Power BI", "data validation", "stakeholder reporting"],
            }
        elif "CANDIDATE BULLET POOL" in user:
            self.calls.append("tailor")
            roles = [
                *master.experience_for(TRACK, "professional"),
                *master.experience_for(TRACK, "additional"),
            ]
            payload = {
                "objective": "Data analyst focused on pipeline validation and reporting.",
                "header_role": "Data Quality Analyst",
                "roles": [
                    {
                        "id": role.id,
                        "bullets": [
                            self._bullet(b)
                            for b in sorted(role.bullets, key=lambda x: -x.priority)[:5]
                        ],
                    }
                    for role in roles
                ],
                "project_ids": [p.id for p in master.projects_for(TRACK)][:2],
                "skill_group_order": list(master.skills.groups())[::-1],
                "certification_ids": [c.id for c in master.certifications_for(TRACK)],
            }
        else:
            self.calls.append("cover")
            payload = {
                "recipient": "Hiring Manager",
                "paragraphs": [
                    "I am writing regarding the Data Quality Analyst position at Northwind Health.",
                    "At TekLink Software Pvt Ltd I applied business-defined data quality rules.",
                    "I would welcome the chance to discuss the role further.",
                ],
            }
        return f"<think>deciding</think>\n```json\n{json.dumps(payload)}\n```"

    def _bullet(self, bullet) -> dict:  # noqa: ANN001
        """Omitting 'text' means keep the approved bullet verbatim -- the default path."""
        if self.fabricate:
            return {"id": bullet.id, "text": bullet.text + " Reduced processing time by 47%."}
        if self.rewrite:
            return {"id": bullet.id, "text": bullet.text.replace("Built", "Engineered")}
        return {"id": bullet.id}


@pytest.fixture
def stubbed(monkeypatch):
    def _install(provider):
        for module in (ingest_nodes, tailor_nodes, cover_nodes):
            monkeypatch.setattr(module, "get_provider", lambda *_, **__: provider)
        return provider

    return _install


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "out_dir", tmp_path / "out")
    connection = sqlite3.connect(str(tmp_path / "graph.db"), check_same_thread=False)
    return build.compile_graph(SqliteSaver(connection))


def _config(name: str) -> dict:
    return {"configurable": {"thread_id": name}, "recursion_limit": 60}


def test_full_run_stops_at_both_gates_and_completes(app, stubbed):
    provider = stubbed(StubProvider())
    config = _config("happy")

    state = app.invoke(
        {
            "application_id": "test-app",
            "track": TRACK,
            "jd_text": "We need a data quality analyst with SQL and Power BI.",
        },
        config,
    )

    assert "__interrupt__" in state, "graph should pause at the resume review gate"
    payload = state["__interrupt__"][0].value
    assert payload["kind"] == "resume"
    assert payload["pages"] == 1, f"fit loop failed: {payload['pages']} pages"
    assert Path(payload["pdf"]).exists()
    assert not payload["violations"], payload["violations"]
    assert payload["coverage"]["score"] > 0

    state = app.invoke(Command(resume={"action": "approve"}), config)
    assert "__interrupt__" in state, "graph should pause at the cover review gate"
    assert state["__interrupt__"][0].value["kind"] == "cover"
    assert Path(state["__interrupt__"][0].value["pdf"]).exists()

    state = app.invoke(Command(resume={"action": "approve"}), config)
    assert state["stage"] == "complete"
    assert Path(state["artifacts"]["resume"]).exists()
    assert Path(state["artifacts"]["cover"]).exists()
    assert provider.calls.count("tailor") == 1


def test_fabricated_metric_is_caught_and_retried(app, stubbed):
    provider = stubbed(StubProvider(fabricate=True))
    state = app.invoke(
        {"application_id": "bad-app", "track": TRACK, "jd_text": "SQL and Power BI."},
        _config("fabricating"),
    )

    payload = state["__interrupt__"][0].value
    assert provider.calls.count("tailor") == settings.max_verify_retries, (
        "verifier should have forced retries"
    )
    assert payload["violations"], "invented metric should reach the human, not be swallowed"
    assert any("47" in v for v in payload["violations"])


def test_rejection_reruns_tailoring_with_feedback(app, stubbed):
    provider = stubbed(StubProvider())
    config = _config("rejecting")
    app.invoke(
        {"application_id": "reject-app", "track": TRACK, "jd_text": "SQL and Power BI."}, config
    )
    assert provider.calls.count("tailor") == 1

    state = app.invoke(
        Command(resume={"action": "reject", "feedback": "lead with the data quality work"}), config
    )
    assert provider.calls.count("tailor") == 2, "rejection should re-enter tailoring"
    assert state["__interrupt__"][0].value["kind"] == "resume"


def test_trim_loop_reduces_an_overflowing_draft(app, stubbed):
    stubbed(StubProvider())
    state = app.invoke(
        {"application_id": "trim-app", "track": "research_data", "jd_text": "SQL."},
        _config("trimming"),
    )
    payload = state["__interrupt__"][0].value
    assert payload["pages"] == 1
    assert payload["trim_log"], "research_data at 5 bullets/role must need trimming"


def _unused() -> None:
    tempfile.gettempdir()


def test_bullets_without_text_are_kept_verbatim(app, stubbed):
    """The model omits 'text' for bullets it is not rewording. Those must come through
    as the approved wording, and must not be re-verified -- there is nothing to invent."""
    stubbed(StubProvider())
    master = MasterResume.load(settings.master_resume)
    pool = master.bullet_pool(TRACK)

    state = app.invoke(
        {"application_id": "verbatim", "track": TRACK, "jd_text": "SQL."}, _config("verbatim")
    )
    payload = state["__interrupt__"][0].value
    assert not payload["violations"]

    for role in payload["draft"]["professional"]:
        for bullet_id, text in zip(role["bullet_ids"], role["bullets"], strict=True):
            assert text == pool[bullet_id].text, f"{bullet_id} was not kept verbatim"


def test_a_reworded_bullet_still_goes_through_verification(app, stubbed):
    stubbed(StubProvider(rewrite=True))
    state = app.invoke(
        {"application_id": "reworded", "track": TRACK, "jd_text": "SQL."}, _config("reworded")
    )
    payload = state["__interrupt__"][0].value
    assert not payload["violations"], "a faithful reword must pass"
    texts = [t for r in payload["draft"]["professional"] for t in r["bullets"]]
    assert any(t.startswith("Engineered") for t in texts), "the reword should have been applied"
