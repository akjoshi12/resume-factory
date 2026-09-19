"""The review pane's own logic, tested without a browser.

Covers the two ways an edit can silently fail to reach the user: the state layer
dropping it, and the preview URL staying identical so the browser serves a cached PDF.
The second one is invisible in every backend test -- the file on disk is correct and
the page still shows the old document.
"""

from __future__ import annotations

from rfactory.state.app_state import AppState, EditBullet, EditSkillGroup


def _state() -> AppState:
    state = AppState(_reflex_internal_init=True)
    state.current_id = "app123"
    state.objective = "original objective"
    state.header_role = "AI Engineer"
    state.bullets = [
        EditBullet(key="tbc:0", role_id="tbc", index=0, bullet_id="tbc_lead",
                   text="ORIGINAL", source="ORIGINAL"),
        EditBullet(key="tbc:1", role_id="tbc", index=1, bullet_id="tbc_eval",
                   text="SECOND", source="SECOND"),
    ]
    state.skill_groups = [EditSkillGroup(key="ai_ml", label="AI & ML", joined="RAG, LangGraph")]
    state._draft = {
        "track": "ai_eng",
        "professional": [
            {
                "id": "tbc",
                "title": "AI Research Intern",
                "org": "Toronto Business College",
                "location": "Toronto, ON",
                "date_range": "Jan 2025 --- Apr 2025",
                "section": "professional",
                "bullet_ids": ["tbc_lead", "tbc_eval"],
                "bullets": ["ORIGINAL", "SECOND"],
            }
        ],
        "additional": [],
        "skills": [{"key": "ai_ml", "label": "AI & ML", "entries": ["RAG", "LangGraph"]}],
        "certifications": [],
        "objective": "original objective",
        "role": "AI Engineer",
    }
    return state


def test_bullet_edit_reaches_the_collected_draft():
    state = _state()
    AppState.set_bullet.fn(state, "tbc:0", "EDITED BY HAND")
    draft = AppState._collected_draft(state)
    assert draft["professional"][0]["bullets"] == ["EDITED BY HAND", "SECOND"]


def test_skill_edit_is_split_back_into_a_list():
    state = _state()
    AppState.set_skill_group.fn(state, "ai_ml", "RAG,  LangGraph , evaluation")
    draft = AppState._collected_draft(state)
    assert draft["skills"][0]["entries"] == ["RAG", "LangGraph", "evaluation"]


def test_objective_and_header_are_carried():
    state = _state()
    state.objective = "new objective"
    state.header_role = "Data Engineer"
    draft = AppState._collected_draft(state)
    assert draft["objective"] == "new objective"
    assert draft["role"] == "Data Engineer"


def test_preview_url_changes_every_time_a_gate_fires():
    """The PDF is rewritten to the same path on every revise. If the URL does not
    change, the browser shows the cached copy and the edit looks like it did nothing."""
    state = _state()
    payload = {"kind": "resume", "draft": state._draft, "pages": 1,
               "coverage": {}, "parse": {}, "violations": [], "trim_log": []}

    AppState._apply_gate(state, payload)
    first = state.resume_pdf_url
    AppState._apply_gate(state, payload)
    second = state.resume_pdf_url

    assert first != second, "preview URL must change or the browser serves a stale PDF"
    assert "app123" in first and first.startswith("http"), "must be absolute, not relative"


def test_cover_preview_url_also_busts_and_is_absolute():
    state = _state()
    AppState._apply_gate(state, {"kind": "cover", "cover": {"paragraphs": ["a"]}, "violations": []})
    first = state.cover_pdf_url
    AppState._apply_gate(state, {"kind": "cover", "cover": {"paragraphs": ["b"]}, "violations": []})
    assert first != state.cover_pdf_url
    assert state.cover_pdf_url.startswith("http")
