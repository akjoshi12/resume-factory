from __future__ import annotations

from pathlib import Path

from langgraph.types import interrupt

from rfactory.config import settings
from rfactory.graph.state import GraphState
from rfactory.models.draft import ResumeDraft
from rfactory.render.fit import trim_once
from rfactory.render.resume import render_pdf, render_tex
from rfactory.scoring import coverage as coverage_mod
from rfactory.scoring import parseback


def _out_dir(state: GraphState) -> Path:
    path = settings.out_dir / state.get("application_id", "scratch")
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_resume(state: GraphState) -> dict:
    draft = ResumeDraft.model_validate(state["draft"])
    tex = render_tex(draft)
    result = render_pdf(draft)

    out = _out_dir(state)
    (out / "resume.tex").write_text(tex, encoding="utf-8")
    (out / "resume.pdf").write_bytes(result.pdf)

    return {
        "resume_tex": tex,
        "resume_pdf_path": str(out / "resume.pdf"),
        "pages": result.pages,
    }


def route_after_render(state: GraphState) -> str:
    if state.get("pages", 0) <= settings.max_pages:
        return "score_resume"
    if int(state.get("fit_attempts") or 0) >= 8:
        return "score_resume"  # give up trimming; the human sees the overflow
    return "trim"


def trim(state: GraphState) -> dict:
    draft = ResumeDraft.model_validate(state["draft"])
    removed = trim_once(draft, state.get("requirements"))
    log = list(state.get("trim_log") or [])
    if removed:
        log.append(removed)
    return {
        "draft": draft.model_dump(),
        "trim_log": log,
        "fit_attempts": int(state.get("fit_attempts") or 0) + (1 if removed else 8),
    }


def score_resume(state: GraphState) -> dict:
    draft = ResumeDraft.model_validate(state["draft"])
    pdf = Path(state["resume_pdf_path"]).read_bytes()

    report = parseback.check(pdf, draft)
    cov = coverage_mod.score(
        state.get("jd_text", ""),
        report.text,
        focus=state.get("requirements") or None,
    )
    return {
        "coverage": {
            "score": cov.score,
            "matched": cov.matched,
            "missing": cov.missing,
            "summary": cov.summary,
        },
        "parse": {
            "ok": report.ok,
            "missing": report.missing,
            "spacing_risk": report.spacing_risk,
            "by_extractor": report.by_extractor,
        },
        "stage": "resume_review",
    }


def review_resume(state: GraphState) -> dict:
    """Human gate. The graph stops here and the checkpointer holds everything until a
    decision arrives, so closing the browser does not lose the application."""
    decision = interrupt(
        {
            "kind": "resume",
            "application_id": state.get("application_id"),
            "draft": state.get("draft"),
            "pages": state.get("pages"),
            "coverage": state.get("coverage"),
            "parse": state.get("parse"),
            "violations": state.get("violations") or [],
            "trim_log": state.get("trim_log") or [],
            "pdf": state.get("resume_pdf_path"),
        }
    )
    action = (decision or {}).get("action", "approve")
    update: dict = {"resume_decision": action}
    if edited := (decision or {}).get("draft"):
        update["draft"] = edited
    if feedback := (decision or {}).get("feedback"):
        update["resume_feedback"] = feedback
    # A model switched at a review gate applies to every step after it, so you
    # can draft cheaply and then re-run the cover letter on something better.
    for key in ("llm_provider", "llm_model"):
        if value := (decision or {}).get(key):
            update[key] = value
    if action == "reject":
        update["violations"] = []
        update["verify_attempts"] = 0
        update["fit_attempts"] = 0
        update["trim_log"] = []
    return update


def route_after_review(state: GraphState) -> str:
    action = state.get("resume_decision", "approve")
    if action == "reject":
        return "tailor"
    if action == "revise":
        return "render_resume"  # user edited fields; recompile and re-score
    return "draft_cover"
