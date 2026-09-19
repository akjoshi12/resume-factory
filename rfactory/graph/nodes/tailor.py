from __future__ import annotations

from rfactory.config import settings
from rfactory.graph.state import GraphState
from rfactory.llm.prompts import REPAIR_USER, TAILOR_SYSTEM, TAILOR_USER
from rfactory.llm.provider import complete_model, get_provider
from rfactory.llm.schemas import Tailoring
from rfactory.models.draft import (
    DraftActivity,
    DraftCertification,
    DraftProject,
    DraftRole,
    ResumeDraft,
    SkillGroup,
)
from rfactory.models.master import MasterResume
from rfactory.render.resume import baseline_draft
from rfactory.scoring.claims import entity_vocabulary, verify_bullet

MAX_BULLETS = 5
MAX_PROJECTS = 3


def _master() -> MasterResume:
    return MasterResume.load(settings.master_resume)


def tailor(state: GraphState) -> dict:
    master = _master()
    track = state["track"]
    pool = master.bullet_pool(track)
    roles = [
        *master.experience_for(track, "professional"),
        *master.experience_for(track, "additional"),
    ]
    projects = master.projects_for(track)
    certs = master.certifications_for(track)

    violations = state.get("violations") or []
    feedback_parts = []
    if violations:
        feedback_parts.append(REPAIR_USER.format(violations="\n".join(violations)))
    if reviewer := (state.get("resume_feedback") or "").strip():
        feedback_parts.append(f"\nREVIEWER FEEDBACK ON THE LAST ATTEMPT:\n{reviewer}")

    user = TAILOR_USER.format(
        requirements="\n".join(f"- {r}" for r in state.get("requirements") or []),
        role_title=state.get("role_title", ""),
        company=state.get("company", ""),
        pool="\n".join(f"{bid}: {b.text}" for bid, b in pool.items()),
        projects="\n".join(f"{p.id}: {p.name}" for p in projects),
        skill_groups="\n".join(f"{k}: {master.group_label(k)}" for k in master.skills.groups()),
        certifications="\n".join(f"{c.id}: {c.name}" for c in certs),
        role_ids=", ".join(r.id for r in roles),
        max_bullets=MAX_BULLETS,
        max_projects=MAX_PROJECTS,
        feedback="\n\n".join(feedback_parts),
    )

    result = complete_model(
        get_provider(state.get("llm_provider"), state.get("llm_model")),
        TAILOR_SYSTEM,
        user,
        Tailoring,
        temperature=0.3,
        max_tokens=settings.max_tokens_tailor,
        acceptable=lambda t: any(r.bullets for r in t.roles),
    )
    return {
        "tailoring": result.model_dump(),
        "verify_attempts": int(state.get("verify_attempts") or 0) + 1,
        "resume_feedback": "",
    }


def verify_claims(state: GraphState) -> dict:
    """Ids must exist in the pool, and no rephrased bullet may carry a fact its source
    does not. Both are deterministic; neither asks a model to police itself."""
    master = _master()
    pool = master.bullet_pool(state["track"])
    vocabulary = entity_vocabulary(master.skill_pool())

    problems: list[str] = []
    for role in (state.get("tailoring") or {}).get("roles", []):
        for bullet in role.get("bullets", []):
            bullet_id, text = bullet.get("id", ""), (bullet.get("text") or "").strip()
            source = pool.get(bullet_id)
            if source is None:
                problems.append(f"{bullet_id}: unknown bullet id, not in the approved pool")
                continue
            if not text:
                continue  # kept verbatim, so there is nothing that could have been invented
            problems += [str(v) for v in verify_bullet(bullet_id, source.text, text, vocabulary)]

    return {"violations": problems}


def route_after_verify(state: GraphState) -> str:
    if not state.get("violations"):
        return "build_draft"
    if int(state.get("verify_attempts") or 0) >= settings.max_verify_retries:
        # Out of retries: carry the violations forward so the human sees exactly what
        # was invented rather than receiving a silently-accepted draft.
        return "build_draft"
    return "tailor"


def build_draft(state: GraphState) -> dict:
    """Assemble the editable draft. Anything the model omitted falls back to the
    deterministic baseline, so a partial response degrades instead of failing."""
    master = _master()
    track = state["track"]
    tailoring = state.get("tailoring") or {}
    pool = master.bullet_pool(track)

    draft = baseline_draft(master, track, role=state.get("role_title", ""))
    chosen = {r.get("id"): r for r in tailoring.get("roles", [])}

    for role in draft.all_roles:
        picked = chosen.get(role.id)
        if not picked:
            continue
        # An omitted text field means "keep the approved bullet as it stands".
        pairs = [
            (b["id"], (b.get("text") or "").strip() or pool[b["id"]].text)
            for b in picked.get("bullets", [])
            if b.get("id") in pool
        ][:MAX_BULLETS]
        if pairs:
            role.bullet_ids = [bid for bid, _ in pairs]
            role.bullets = [text for _, text in pairs]

    if ids := [pid for pid in tailoring.get("project_ids", []) if pid]:
        by_id = {p.id: p for p in master.projects_for(track)}
        selected = [by_id[pid] for pid in ids if pid in by_id][:MAX_PROJECTS]
        if selected:
            draft.projects = [
                DraftProject(
                    id=p.id,
                    name=f"{p.name} - {p.subtitle}" if p.subtitle else p.name,
                    bullet_ids=[b.id for b in sorted(p.bullets, key=lambda x: -x.priority)[:2]],
                    bullets=[b.text for b in sorted(p.bullets, key=lambda x: -x.priority)[:2]],
                )
                for p in selected
            ]

    if order := [k for k in tailoring.get("skill_group_order", []) if k in master.skills.groups()]:
        groups = master.skills.groups()
        ordered = order + [k for k in groups if k not in order]
        draft.skills = [
            SkillGroup(key=k, label=master.group_label(k), entries=groups[k]) for k in ordered
        ]

    if cert_ids := [c for c in tailoring.get("certification_ids", []) if c]:
        by_id = {c.id: c for c in master.certifications_for(track)}
        picked_certs = [by_id[c] for c in cert_ids if c in by_id]
        if picked_certs:
            draft.certifications = [
                DraftCertification(name=c.name, issuer=c.issuer) for c in picked_certs
            ]

    if objective := (tailoring.get("objective") or "").strip():
        draft.objective = objective
    if header := (tailoring.get("header_role") or "").strip():
        draft.role = header

    _ = (DraftRole, DraftActivity)  # re-exported for the UI layer
    return {"draft": draft.model_dump(), "stage": "rendering"}
