"""One-page enforcement.

Trimming is deterministic rather than a re-prompt: re-asking the model to "write
shorter" spends a generation, is slow on a local model, and reopens the fabrication
surface for no benefit.

Which item to drop is chosen by relevance to the job posting, not by the master
priority alone. Priority encodes how good a bullet is in general; the posting decides
what matters today. Trimming on priority alone reliably deletes the bullet that
matched the requirement -- the exact opposite of tailoring.
"""

from __future__ import annotations

from rfactory.models.draft import DraftRole, ResumeDraft
from rfactory.scoring.coverage import terms


def _relevance(text: str, wanted: set[str]) -> int:
    return len(terms(text) & wanted) if wanted else 0


def _weakest_bullet(roles: list[DraftRole], wanted: set[str], floor: int) -> tuple[DraftRole, int] | None:
    """The least JD-relevant bullet across roles that can still spare one. Ties break
    toward the later bullet, which is the lower-priority one after selection."""
    candidates = [
        (_relevance(role.bullets[i], wanted), -i, role, i)
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


def trim_once(draft: ResumeDraft, requirements: list[str] | None = None) -> str | None:
    """Remove the single least valuable item. Returns a description of what went, or
    None when nothing more can go without gutting the document."""
    wanted = {t for phrase in (requirements or []) for t in terms(phrase)}

    if draft.activities:
        removed = draft.activities.pop()
        return f"dropped activity '{removed.title}'"

    if found := _weakest_bullet(draft.all_roles, wanted, floor=2):
        role, index = found
        bullet_id = role.bullet_ids.pop(index)
        role.bullets.pop(index)
        return f"dropped bullet {bullet_id} from {role.id} (lowest JD relevance)"

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

    if len(draft.certifications) > 1:
        target = min(draft.certifications, key=lambda c: _relevance(c.name, wanted))
        draft.certifications.remove(target)
        return f"dropped certification '{target.name}'"

    if found := _weakest_bullet(draft.all_roles, wanted, floor=1):
        role, index = found
        bullet_id = role.bullet_ids.pop(index)
        role.bullets.pop(index)
        return f"dropped bullet {bullet_id} from {role.id} (last resort)"

    return None
