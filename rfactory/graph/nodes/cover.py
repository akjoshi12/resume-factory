from __future__ import annotations

from pathlib import Path

from langgraph.types import interrupt

from rfactory.config import settings
from rfactory.graph.state import GraphState
from rfactory.llm.prompts import COVER_SYSTEM, COVER_USER
from rfactory.llm.provider import LLMError, complete_model, get_provider
from rfactory.llm.schemas import CoverLetterBody
from rfactory.models.draft import CoverLetterDraft, ResumeDraft
from rfactory.models.master import MasterResume
from rfactory.render.resume import render_cover_pdf
from rfactory.scoring.claims import entity_vocabulary, verify_letter
from rfactory.scoring.coverage import terms


def _resume_summary(draft: ResumeDraft) -> str:
    lines = [f"OBJECTIVE: {draft.objective}"] if draft.objective else []
    for role in draft.all_roles:
        lines.append(f"\n{role.title}, {role.org} ({role.date_range})")
        lines += [f"  - {b}" for b in role.bullets]
    for project in draft.projects:
        lines.append(f"\nPROJECT {project.name}")
        lines += [f"  - {b}" for b in project.bullets]
    return "\n".join(lines)


def draft_cover(state: GraphState) -> dict:
    master = MasterResume.load(settings.master_resume)
    draft = ResumeDraft.model_validate(state["draft"])

    feedback = ""
    if reviewer := (state.get("cover_feedback") or "").strip():
        feedback = f"\nREVIEWER FEEDBACK ON THE LAST ATTEMPT:\n{reviewer}"

    body = complete_model(
        get_provider(state.get("llm_provider"), state.get("llm_model")),
        COVER_SYSTEM,
        COVER_USER.format(
            role_title=state.get("role_title", ""),
            company=state.get("company", ""),
            requirements="\n".join(f"- {r}" for r in state.get("requirements") or []),
            resume_summary=_resume_summary(draft),
            feedback=feedback,
        ),
        CoverLetterBody,
        temperature=0.4,
        max_tokens=settings.max_tokens_cover,
        acceptable=lambda body: len([p for p in body.paragraphs if p.strip()]) >= 2,
    )

    paragraphs = [p.strip() for p in body.paragraphs if p and p.strip()]
    if not paragraphs:
        raise LLMError(
            "the model returned a cover letter with no body paragraphs. Rendering it "
            "would produce a greeting and a signature with nothing between them, so "
            "this fails here instead."
        )
    body.paragraphs = paragraphs

    # Checked against the whole resume it accompanies, not bullet by bullet, since a
    # paragraph legitimately draws on several at once. The posting is context: words
    # the employer used are notes, not violations.
    source = _resume_summary(draft)
    vocabulary = entity_vocabulary(master.skill_pool()) | {
        w.lower() for w in (state.get("company", "") + " " + state.get("role_title", "")).split()
    }
    context = terms(state.get("jd_text", "")) | {
        t for requirement in (state.get("requirements") or []) for t in terms(requirement)
    }

    violations: list[str] = []
    notes: list[str] = []
    for index, paragraph in enumerate(body.paragraphs):
        bad, soft = verify_letter(f"cover-p{index + 1}", source, paragraph, vocabulary, context)
        violations += [str(v) for v in bad]
        notes += soft

    cover = CoverLetterDraft(
        profile=master.profile,
        title=draft.role,
        recipient=body.recipient or "Hiring Manager",
        company=state.get("company", ""),
        paragraphs=body.paragraphs,
    )
    return {
        "cover": cover.model_dump(),
        "violations": violations,
        "notes": notes,
        "cover_feedback": "",
    }


def render_cover(state: GraphState) -> dict:
    cover = CoverLetterDraft.model_validate(state["cover"])
    result = render_cover_pdf(cover)
    out = settings.out_dir / state.get("application_id", "scratch")
    out.mkdir(parents=True, exist_ok=True)
    (out / "cover.pdf").write_bytes(result.pdf)
    return {"cover_pdf_path": str(out / "cover.pdf"), "stage": "cover_review"}


def review_cover(state: GraphState) -> dict:
    decision = interrupt(
        {
            "kind": "cover",
            "application_id": state.get("application_id"),
            "cover": state.get("cover"),
            "violations": state.get("violations") or [],
            "notes": state.get("notes") or [],
            "pdf": state.get("cover_pdf_path"),
        }
    )
    action = (decision or {}).get("action", "approve")
    update: dict = {"cover_decision": action}
    if edited := (decision or {}).get("cover"):
        update["cover"] = edited
    if feedback := (decision or {}).get("feedback"):
        update["cover_feedback"] = feedback
    # A model switched at a review gate applies to every step after it, so you
    # can draft cheaply and then re-run the cover letter on something better.
    for key in ("llm_provider", "llm_model"):
        if value := (decision or {}).get(key):
            update[key] = value
    return update


def route_after_cover_review(state: GraphState) -> str:
    action = state.get("cover_decision", "approve")
    if action == "reject":
        return "draft_cover"
    if action == "revise":
        return "render_cover"
    return "finalize"


def finalize(state: GraphState) -> dict:
    paths = {
        "resume": state.get("resume_pdf_path"),
        "cover": state.get("cover_pdf_path"),
    }
    _ = Path  # keep the import meaningful for downstream typing
    return {"stage": "complete", "artifacts": paths}
