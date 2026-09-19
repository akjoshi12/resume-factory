from __future__ import annotations

from rfactory.config import settings
from rfactory.models.draft import (
    CoverLetterDraft,
    DraftActivity,
    DraftCertification,
    DraftEducation,
    DraftProject,
    DraftRole,
    ResumeDraft,
    SkillGroup,
)
from rfactory.models.master import Bullet, Experience, MasterResume, Project
from rfactory.render.latex import CompileResult, compile_tex, make_env

# Copied alongside the generated .tex at compile time.
RESUME_AUX = ("TLCresume.sty", "_header.tex")


def _top(bullets: list[Bullet], n: int) -> list[Bullet]:
    return sorted(bullets, key=lambda b: -b.priority)[:n]


def _role(exp: Experience, n: int) -> DraftRole:
    chosen = _top(exp.bullets, n)
    return DraftRole(
        id=exp.id,
        org=exp.org,
        title=exp.title,
        location=exp.location,
        date_range=exp.date_range,
        section=exp.section,
        bullet_ids=[b.id for b in chosen],
        bullets=[b.text for b in chosen],
    )


def _project(project: Project, n: int) -> DraftProject:
    chosen = _top(project.bullets, n)
    return DraftProject(
        id=project.id,
        name=f"{project.name} - {project.subtitle}" if project.subtitle else project.name,
        bullet_ids=[b.id for b in chosen],
        bullets=[b.text for b in chosen],
    )


def baseline_draft(
    master: MasterResume,
    track: str,
    *,
    role: str = "",
    bullets_per_role: int = 4,
    max_projects: int = 2,
    project_bullets: int = 2,
    include_certifications: bool = True,
    include_activities: bool = False,
) -> ResumeDraft:
    """Deterministic draft: track filter plus priority ordering, no model involved.
    The floor the LLM has to beat, and the fixture the smoke test compiles."""
    projects = sorted(
        master.projects_for(track),
        key=lambda p: -max((b.priority for b in p.bullets), default=0),
    )[:max_projects]

    return ResumeDraft(
        track=track,
        profile=master.profile,
        role=role or master.profile.role_default,
        objective="",
        skills=[
            SkillGroup(key=key, label=master.group_label(key), entries=entries)
            for key, entries in master.skills.groups().items()
        ],
        professional=[
            _role(e, bullets_per_role) for e in master.experience_for(track, "professional")
        ],
        additional=[_role(e, 1) for e in master.experience_for(track, "additional")],
        projects=[_project(p, project_bullets) for p in projects],
        education=[
            DraftEducation(
                credential=e.credential,
                institution=e.institution,
                location=e.location,
                date_range=e.date_range,
            )
            for e in master.education
        ],
        certifications=(
            [
                DraftCertification(name=c.name, issuer=c.issuer)
                for c in master.certifications_for(track)
            ]
            if include_certifications
            else []
        ),
        activities=(
            [DraftActivity(title=a.title, dates=a.dates) for a in master.activities_for(track)]
            if include_activities
            else []
        ),
    )


def render_tex(draft: ResumeDraft) -> str:
    return make_env().get_template("resume.tex.j2").render(**draft.template_context())


def render_pdf(draft: ResumeDraft) -> CompileResult:
    return compile_tex(
        render_tex(draft),
        jobname="resume",
        aux_files={name: settings.templates_dir / name for name in RESUME_AUX},
    )


# -- cover letter -------------------------------------------------------------


def render_cover_pdf(draft: CoverLetterDraft) -> CompileResult:
    """main.tex is static and \\input{info} + \\input{body}; we generate those two."""
    env = make_env()
    ctx = draft.template_context()
    main = (settings.templates_dir / "cover" / "main.tex").read_text(encoding="utf-8")
    return compile_tex(
        main,
        jobname="main",
        extra_sources={
            "info.tex": env.get_template("cover/info.tex.j2").render(**ctx),
            "body.tex": env.get_template("cover/body.tex.j2").render(**ctx),
        },
    )
