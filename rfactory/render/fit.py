"""One-page enforcement.

Trimming is deterministic rather than a re-prompt: re-asking the model to "write
shorter" spends a generation, is slow on a local model, and reopens the fabrication
surface for no benefit.

Work experience goes last: projects, extra skill groups and certifications are cut
before any role loses a bullet below two. Cutting work bullets first used to leave a
resume of AI side projects with two-bullet jobs, for a data engineering posting.

Which item to drop is chosen by relevance to the job posting, not by the master
priority alone. Priority encodes how good a bullet is in general; the posting decides
what matters today. Trimming on priority alone reliably deletes the bullet that
matched the requirement -- the exact opposite of tailoring.
"""

from __future__ import annotations

from rfactory.models.draft import DraftRole, ResumeDraft
from rfactory.scoring.claims import mentions
from rfactory.scoring.coverage import keywords

# Postings and bullets name the same work differently: "troubleshoot failures" vs
# "investigated a degraded load". Without this, the bullet that did exactly what the
# posting asks scores zero and is the first to go. ponytail: a short hand-kept list.
_SYNONYMS = [
    ["troubleshoot", "investigate", "diagnose", "debug", "resolve", "root-cause"],
    ["validate", "validation", "check", "test", "reconcile", "reconciliation", "quality"],
    ["document", "documentation", "runbook", "definitions"],
    ["build", "develop", "implement", "maintain"],
    ["ingest", "ingestion", "load", "extract", "etl", "elt"],
    ["dashboard", "report", "reporting", "visualization"],
    ["stakeholder", "client", "business", "leadership"],
]
_SYNONYM_STEMS = [set().union(*(keywords(w) for w in group)) for group in _SYNONYMS]


def _expand(words: set[str]) -> set[str]:
    out = set(words)
    for group in _SYNONYM_STEMS:
        if words & group:
            out |= group
    return out


def _relevance(text: str, wanted: set[str]) -> int:
    return len(keywords(text) & wanted) if wanted else 0


def bullet_relevance(text: str, wanted: set[str], tools: list[str] | None = None) -> float:
    """How much a bullet answers the posting. A raw overlap count rewarded long,
    tool-dense bullets (an AI internship listing eight libraries) over a short bullet
    that matched a requirement outright, so it is divided by the square root of the
    bullet's length. A posting tool named in the bullet is the strongest signal of all."""
    words = keywords(text)
    if not words or not (wanted or tools):
        return 0.0
    overlap = len(_expand(words) & wanted) / len(words) ** 0.5
    return overlap + 2.0 * sum(1 for t in tools or [] if mentions(text, t))


def _weakest_bullet(
    roles: list[DraftRole], wanted: set[str], floor: int, tools: list[str] | None = None
) -> tuple[DraftRole, int] | None:
    """The least JD-relevant bullet across roles that can still spare one. Ties break
    toward the later bullet, which is the lower-priority one after selection."""
    candidates = [
        (bullet_relevance(role.bullets[i], wanted, tools), -i, role, i)
        for role in roles
        if len(role.bullets) > floor
        for i in range(len(role.bullets))
    ]
    if not candidates:
        return None
    # Compare on the scores only: DraftRole is not orderable, so a tie on both keys
    # would otherwise fall through to comparing the models themselves.
    score, _, role, index = min(candidates, key=lambda c: (c[0], c[1]))
    return role, index


def trim_once(
    draft: ResumeDraft, requirements: list[str] | None = None, tools: list[str] | None = None
) -> str | None:
    """Remove the single least valuable item. Returns a description of what went, or
    None when nothing more can go without gutting the document."""
    wanted = {t for phrase in (requirements or []) for t in keywords(phrase)}

    if draft.activities:
        removed = draft.activities.pop()
        return f"dropped activity '{removed.title}'"

    projects = [p for p in draft.projects if len(p.bullets) > 1]
    if projects:
        target = min(projects, key=lambda p: _relevance(" ".join(p.bullets), wanted))
        bullet_id = target.bullet_ids.pop()
        target.bullets.pop()
        return f"dropped bullet {bullet_id} from project {target.id}"

    if len(draft.projects) > 1:
        target = min(draft.projects, key=lambda p: _relevance(p.name + " ".join(p.bullets), wanted))
        draft.projects.remove(target)
        return f"dropped project '{target.name}'"

    # A skill line is the cheapest carrier of a posting keyword: only a group matching
    # nothing in the posting goes. Dropping 'Languages' took Python off a Python job.
    idle = [g for g in draft.skills if not _relevance(" ".join(g.entries), wanted)]
    if len(draft.skills) > 3 and idle:
        removed = idle[-1]
        draft.skills.remove(removed)
        return f"dropped skill group '{removed.label}'"

    if len(draft.certifications) > 1:
        target = min(draft.certifications, key=lambda c: _relevance(c.name, wanted))
        draft.certifications.remove(target)
        return f"dropped certification '{target.name}'"

    if found := _weakest_bullet(draft.all_roles, wanted, floor=2, tools=tools):
        role, index = found
        bullet_id = role.bullet_ids.pop(index)
        role.bullets.pop(index)
        return f"dropped bullet {bullet_id} from {role.id} (lowest JD relevance)"

    if found := _weakest_bullet(draft.all_roles, wanted, floor=1, tools=tools):
        role, index = found
        bullet_id = role.bullet_ids.pop(index)
        role.bullets.pop(index)
        return f"dropped bullet {bullet_id} from {role.id} (last resort)"

    return None
