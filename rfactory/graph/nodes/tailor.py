from __future__ import annotations

import re

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
from rfactory.models.master import Bullet, Experience, MasterResume
from rfactory.render.fit import bullet_relevance
from rfactory.render.resume import baseline_draft
from rfactory.scoring.ats import phrases_found
from rfactory.scoring.claims import (
    absent_tools,
    dropped_keywords,
    entity_vocabulary,
    mentions,
    tool_violations,
    verify_bullet,
)
from rfactory.scoring.coverage import keywords as content_words

MAX_BULLETS = 5
# A role not tagged for this track (an AI internship on a data engineering resume)
# keeps at most this many bullets, so the on-track role carries the page.
OFF_TRACK_BULLETS = 2
MAX_PROJECTS = 3

# "3+ years", "2 yrs", "five years of experience" -- the objective is where a model
# most likes to invent a tenure, and no source bullet can license one.
_YEARS = re.compile(
    r"\b(\d+\+?|one|two|three|four|five|six|seven|eight|nine|ten)\s*\+?\s*(years?|yrs?)\b",
    re.IGNORECASE,
)


def _clean_header(header: str, company: str) -> str:
    """The header is a bare title. Models like to print 'Data Engineer at Acme'."""
    header = re.split(r"\s+(?:at|@)\s+", header.strip(), maxsplit=1)[0]
    if company.strip():
        header = re.sub(re.escape(company.strip()), "", header, flags=re.IGNORECASE)
    return " ".join(header.split()).strip(" -,")


def _master() -> MasterResume:
    return MasterResume.load(settings.master_resume)


def _forbidden(master: MasterResume, state: GraphState) -> list[str]:
    """Posting tools the candidate never used, plus posting keyword phrases naming an
    industry they have no history in ('financial reporting'): both used to be handed to
    the model as targets and came back as claims."""
    claimable = master.claimable_text()
    return absent_tools(state.get("tools") or [], claimable) + unclaimable_domains(
        state.get("keywords") or [], claimable
    )


def unclaimable_domains(phrases: list[str], source: str) -> list[str]:
    return [p for p in phrases if _borrowed_terms("", p, source)]


def tailor(state: GraphState) -> dict:
    master = _master()
    track = state["track"]
    roles = [
        *master.experience_for(track, "professional"),
        *master.experience_for(track, "additional"),
    ]
    # Every project and certification is on offer, whatever the track: the track is
    # picked by hand and a wrong pick (an AI track for a data engineering posting)
    # used to print AI projects on a data engineering resume.
    projects = master.projects
    certs = master.certifications

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
        forbidden=", ".join(_forbidden(master, state)) or "(none)",
        keywords=", ".join(
            k for k in state.get("keywords") or [] if k not in _forbidden(master, state)
        ) or "(none)",
        pool="\n\n".join(
            f"[{r.id}] {r.title}, {r.org}\n"
            + "\n".join(f"  {b.id}: {b.text}" for b in r.bullets)
            for r in roles
        ),
        projects="\n".join(
            f"{p.id}: {p.name}: {p.bullets[0].text if p.bullets else p.subtitle}" for p in projects
        ),
        skill_groups="\n".join(
            f"{k}: {master.group_label(k)}: {', '.join(v)}"
            for k, v in master.skills.groups().items()
        ),
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

    owners = master.role_bullets(state["track"])

    problems: list[str] = []
    tailoring = state.get("tailoring") or {}
    forbidden = _forbidden(master, state)
    terms = posting_terms(state)
    problems += _objective_problems(
        master,
        tailoring.get("objective") or "",
        forbidden,
        vocabulary | _target_words(state),
        terms,
    )
    claimable = master.claimable_text()
    for role in tailoring.get("roles", []):
        own = owners.get(role.get("id", ""), {})
        for bullet in role.get("bullets", []):
            bullet_id, text = bullet.get("id", ""), (bullet.get("text") or "").strip()
            source = pool.get(bullet_id)
            if source is None:
                problems.append(f"{bullet_id}: unknown bullet id, not in the approved pool")
                continue
            if bullet_id not in own:
                problems.append(
                    f"{bullet_id}: belongs to a different role or a project, not "
                    f"{role.get('id')}; a bullet may only appear under its own role"
                )
                continue
            if not text:
                continue  # kept verbatim, so there is nothing that could have been invented
            problems += [str(v) for v in verify_bullet(bullet_id, source.text, text, vocabulary)]
            problems += tool_violations(bullet_id, text, forbidden)
            problems += dropped_keywords(bullet_id, source.text, text, vocabulary)
            problems += _borrowed_terms(bullet_id, text, claimable)
            problems += _injected_terms(bullet_id, text, source.text, terms)

    return {"violations": problems}


def _target_words(state: GraphState) -> set[str]:
    """Naming the role being applied for is the point of an objective, not a claim. The
    company is not allowed: 'Northgate Financial' let 'financial data' through."""
    return {w.lower().strip(",.()") for w in state.get("role_title", "").split()}


# Industries a posting names and a model likes to adopt as the candidate's own. Matching
# every posting word instead flagged "requirements" and "stakeholders" and cost the
# objective. ponytail: hand-kept list; add an industry when one slips through.
DOMAINS = {
    "financ", "banking", "bank", "insura", "health", "clinic", "hospit", "pharma", "retail",
    "ecomme", "e-comm", "logist", "supply", "invent", "teleco", "manufa", "accoun",
    "payrol", "market", "sales", "fintec", "credit", "lendin", "mortga",
}


def _borrowed_terms(label: str, text: str, source: str) -> list[str]:
    """Industry words the candidate's material never mentions: 'financial reporting' on
    a resume with no finance work. Lowercase, so they pass the entity check."""
    have = {w[:6] for w in content_words(source)}
    borrowed = sorted(
        w for w in content_words(text) if w[:6] in DOMAINS and w[:6] not in have
    )
    if not borrowed:
        return []
    return [f"{label}: claims {', '.join(borrowed)} experience the candidate does not have; "
            "remove it"]


def posting_terms(state: GraphState) -> set[str]:
    """Content stems of the posting's keyword phrases and tools."""
    phrases = [*(state.get("keywords") or []), *(state.get("tools") or [])]
    return {t for phrase in phrases for t in content_words(phrase)}


# Words every posting and every bullet share; flagging them only adds noise.
_GENERIC_TERMS = {"data"}


def _injected_terms(label: str, text: str, source: str, terms: set[str]) -> list[str]:
    """Posting vocabulary the rewrite adds and its source never had. The entity check
    misses these because they are lowercase or already in the skill pool: a live run
    turned a quality-rules bullet into 'data quality checks, anomaly detection' and a
    SQL bullet into 'SQL and Python transformations' -- both printed, both untrue."""
    if not terms:
        return []
    added = sorted((content_words(text) - content_words(source)) & terms - _GENERIC_TERMS)
    if not added:
        return []
    return [f"{label}: adds posting terms its source never claims ({', '.join(added)}); "
            "say only what the source says"]


def _restates_posting(objective: str, source: str) -> list[str]:
    """An objective whose words mostly appear nowhere in the candidate's material is the
    posting's duty list in the first person ('load financial data into KPI data marts').
    Measured: posting copies run near 50% unsupported words, honest summaries 0-31%."""
    have = {w[:6] for w in content_words(source)}
    words = content_words(objective)
    unsupported = sorted(w for w in words if w[:6] not in have)
    if len(unsupported) >= 6 and len(unsupported) > 0.4 * len(words):
        return [
            "objective: restates the posting instead of the candidate's experience "
            f"({', '.join(unsupported[:8])}); describe only what the bullets show"
        ]
    return []


def _objective_problems(
    master: MasterResume,
    objective: str,
    forbidden: list[str],
    vocabulary: set[str],
    terms: set[str] | None = None,
) -> list[str]:
    """The objective is free prose, so it gets the bullet rule against everything the
    candidate can claim. Before this it was unchecked, and printed 'skilled in dbt and
    Airflow' for a candidate who has used neither."""
    if not objective:
        return []
    source = master.claimable_text()
    problems = [str(v) for v in verify_bullet("objective", source, objective, vocabulary)]
    problems += tool_violations("objective", objective, forbidden)
    problems += _restates_posting(objective, source)
    problems += _borrowed_terms("objective", objective, source)
    problems += _injected_terms("objective", objective, source, terms or set())
    if _YEARS.search(objective):
        problems.append("objective: states a years-of-experience figure; remove it")
    return problems


def route_after_verify(state: GraphState) -> str:
    if not state.get("violations"):
        return "build_draft"
    if int(state.get("verify_attempts") or 0) >= settings.max_verify_retries:
        # Out of retries: carry the violations forward so the human sees exactly what
        # was invented rather than receiving a silently-accepted draft.
        return "build_draft"
    return "tailor"


def _safe_text(
    bullet: dict,
    source: str,
    forbidden: list[str],
    vocabulary: set[str],
    terms: set[str] | None = None,
) -> str:
    """The rewrite, unless it still carries an invented fact after the retries ran out;
    then the approved source text. A violation never reaches the PDF."""
    text = (bullet.get("text") or "").strip()
    if not text:
        return source
    bad = verify_bullet(bullet["id"], source, text, vocabulary)
    bad = bad or tool_violations("", text, forbidden)
    bad = bad or dropped_keywords("", source, text, vocabulary)
    bad = bad or _injected_terms("", text, source, terms or set())
    return source if bad else text


def _posting_phrases(state: GraphState) -> list[str]:
    return list(dict.fromkeys([*(state.get("keywords") or []), *(state.get("tools") or [])]))


def _coverage(text: str, phrases: list[str]) -> int:
    return len(phrases_found(phrases, text))


def best_phrasing(current: str, source: Bullet, phrases: list[str]) -> str:
    """Of the approved phrasings of one fact -- the model's checked rewrite, the source,
    and its hand-written variants -- the one carrying the most posting phrases. Ties keep
    the current text. Every candidate is human-approved or already verified, so coverage
    goes up without a model writing anything new."""
    if not phrases:
        return current
    candidates = [current, source.text, *source.variants]
    return max(candidates, key=lambda t: (_coverage(t, phrases), t == current))


def _alias_hit(alias: str, phrases: list[str]) -> bool:
    have = content_words(alias)
    return bool(have) and any(
        (want := content_words(p)) and (want <= have or have <= want) for p in phrases
    )


def skill_entries(master: MasterResume, entries: list[str], phrases: list[str]) -> list[str]:
    """A group's entries in the posting's own words, posting matches first. When the
    posting names a skill by an alias ('Version Control' for 'Git', 'Data Ingestion' for
    'ETL/ELT Pipelines'), the alias is printed INSTEAD of the entry -- printing both made
    the line read like a keyword dump."""
    if not phrases:
        return list(entries)
    units: list[tuple[bool, list[str]]] = []
    seen: set[str] = set()
    for entry in entries:
        aliases = [
            a for a in master.skill_aliases.get(entry, [])
            if a not in seen and a not in entries and _alias_hit(a, phrases)
        ]
        if aliases and "(" not in entry:
            # "Git (Version Control)": keeps the tool name ATS matches on and adds the
            # posting's word, in a form a person reads as one skill.
            shown, hit = [f"{entry} ({aliases[0]})"], True
        elif _alias_hit(entry, phrases):
            shown, hit = [entry], True
        elif aliases:
            shown, hit = [aliases[0]], True
        else:
            shown, hit = [entry], False
        seen.update(shown)
        units.append((hit, shown))
    return [e for hit, shown in units if hit for e in shown] + [
        e for hit, shown in units if not hit for e in shown
    ]


def _off_track_roles(master: MasterResume, track: str, state: GraphState) -> set[str]:
    """Professional roles not tagged for this track -- except the role that best
    answers the posting. The track is picked by hand, and a wrong pick (an AI track for
    a data engineering posting) must not cap the one role that matches the job."""
    wanted = {t for phrase in state.get("requirements") or [] for t in content_words(phrase)}
    tools = state.get("tools") or []
    roles = [e for e in master.experience if e.section == "professional"]
    if not roles:
        return set()

    def fit(role: Experience) -> float:
        scores = sorted(
            (bullet_relevance(b.text, wanted, tools) for b in role.bullets), reverse=True
        )
        return sum(scores[:3])

    best = max(roles, key=fit).id
    return {e.id for e in roles if track not in e.tracks and e.id != best}


def build_draft(state: GraphState) -> dict:
    """Assemble the editable draft. Anything the model omitted falls back to the
    deterministic baseline, so a partial response degrades instead of failing."""
    master = _master()
    track = state["track"]
    tailoring = state.get("tailoring") or {}

    draft = baseline_draft(master, track, role=state.get("role_title", ""))
    chosen = {r.get("id"): r for r in tailoring.get("roles", [])}

    owners = master.role_bullets(track)
    forbidden = _forbidden(master, state)
    vocabulary = entity_vocabulary(master.skill_pool())
    off_track = _off_track_roles(master, track, state)
    terms = posting_terms(state)
    phrases = _posting_phrases(state)
    for role in draft.all_roles:
        picked = chosen.get(role.id)
        if not picked:
            continue
        own = owners.get(role.id, {})
        # An omitted text field means "keep the approved bullet as it stands". A bullet
        # from another role or a project is dropped here even if verification ran out
        # of retries: misattributed work is worse than a shorter role.
        pairs = [
            (b["id"], _safe_text(b, own[b["id"]].text, forbidden, vocabulary, terms))
            for b in picked.get("bullets", [])
            if b.get("id") in own
        ]
        # The top-priority bullet says what the role WAS ("Led an 8-person team that
        # built..."). Without it a capped role reads as two stray details.
        if pairs and role.section == "professional" and own:
            lead = max(own.values(), key=lambda b: b.priority)
            if lead.id not in {bid for bid, _ in pairs}:
                pairs.insert(0, (lead.id, lead.text))
        pairs = pairs[: OFF_TRACK_BULLETS if role.id in off_track else MAX_BULLETS]
        pairs = [(bid, best_phrasing(text, own[bid], phrases)) for bid, text in pairs]
        # Never let filtering starve a role: top up from its own best bullets.
        floor = 1 if role.section == "additional" else 2
        if pairs and len(pairs) < floor:
            used = {bid for bid, _ in pairs}
            spare = sorted((b for b in own.values() if b.id not in used), key=lambda b: -b.priority)
            pairs += [(b.id, b.text) for b in spare[: floor - len(pairs)]]
        if pairs:
            role.bullet_ids = [bid for bid, _ in pairs]
            role.bullets = [text for _, text in pairs]

    if ids := [pid for pid in tailoring.get("project_ids", []) if pid]:
        by_id = {p.id: p for p in master.projects}
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
        # Only the groups that help: seven groups made a quarter-page table above the
        # experience. A group the model skipped still shows if it holds a posting tool.
        tools = state.get("tools") or []
        ordered = order + [
            k for k in groups
            if k not in order and any(mentions(e, t) for e in groups[k] for t in tools)
        ]
        draft.skills = [
            SkillGroup(
                key=k,
                label=master.group_label(k),
                entries=skill_entries(master, groups[k], phrases),
            )
            for k in ordered
        ]

    if cert_ids := [c for c in tailoring.get("certification_ids", []) if c]:
        by_id = {c.id: c for c in master.certifications}
        picked_certs = [by_id[c] for c in cert_ids if c in by_id]
        if picked_certs:
            draft.certifications = [
                DraftCertification(name=c.name, issuer=c.issuer) for c in picked_certs
            ]

    objective = (tailoring.get("objective") or "").strip()
    # Out of retries with a bad objective: print none rather than an invented one.
    allowed = vocabulary | _target_words(state)
    if objective and not _objective_problems(master, objective, forbidden, allowed, terms):
        draft.objective = objective
    elif fallback := master.objectives.get(track, "").strip():
        # A failed objective used to leave the resume with no summary at all. The
        # per-track fallback is hand-written and approved, so it needs no checking.
        draft.objective = fallback
    if header := _clean_header(tailoring.get("header_role") or "", state.get("company", "")):
        draft.role = header

    _ = (DraftRole, DraftActivity)  # re-exported for the UI layer
    return {"draft": draft.model_dump(), "stage": "rendering"}
