from __future__ import annotations

import re
from pathlib import Path

from langgraph.types import interrupt

from rfactory.config import settings
from rfactory.graph.nodes.tailor import _YEARS, _borrowed_terms, unclaimable_domains
from rfactory.graph.state import GraphState
from rfactory.llm.prompts import COVER_SYSTEM, COVER_USER
from rfactory.llm.provider import LLMError, complete_model, get_provider
from rfactory.llm.schemas import CoverLetterBody
from rfactory.models.draft import CoverLetterDraft, ResumeDraft
from rfactory.models.master import MasterResume
from rfactory.render.resume import render_cover_pdf
from rfactory.scoring.claims import (
    absent_tools,
    entity_vocabulary,
    mentions,
    tool_violations,
    verify_letter,
)
from rfactory.scoring.coverage import terms

MAX_POSTING_CHARS = 6000
_OPENER = re.compile(
    r"^I am writing to (?:apply for|express my (?:strong )?interest in)", re.IGNORECASE
)
PASTE_WORDS = 15  # this many consecutive words lifted from one bullet is a paste
CLICHES = (
    "which directly supports", "aligns directly with", "i am confident", "highly motivated",
    "proven track record", "i believe", "passionate", "i am writing to",
    "the posting", "the job description", "strong fit", "great fit",
)
# "This experience directly supports your need for X": the stock bridge a model adds after
# every story. A fixed phrase list missed each new verb, so match the shape instead.
_BRIDGE = re.compile(
    r"\b(?:this|that|which|these|such)\b[^.!?]{0,80}?\b(?:supports?|answers?|address(?:es)?|"
    r"meets?|match(?:es)?|maps?(?: directly)? to|aligns? with|speaks? to|fulfil+s?|"
    r"prepares? me for)\b[^.!?]{0,40}?\byour\b[^.!?]{0,25}?\b(?:needs?|requirements?|"
    r"focus|goals?|priorit(?:y|ies)|emphasis)\b",
    re.IGNORECASE,
)
MIN_WORDS, MAX_WORDS = 400, 510  # 12pt fills one page at ~420-460; 11.5pt absorbs up to ~510
STACK_LIMIT = 6  # this many of the candidate's own tools in one sentence is a pasted stack


def _style_problems(
    label: str, paragraph: str, bullets: list[str], skills: set[str] | frozenset = frozenset()
) -> list[str]:
    """What made the letters read as machine output: whole bullets pasted in, and the
    same stock phrases every time. Both are cheap to detect exactly."""
    words = paragraph.lower().split()
    grams = {" ".join(words[i : i + PASTE_WORDS]) for i in range(len(words) - PASTE_WORDS + 1)}
    pasted = [g for g in grams if any(g in " ".join(b.lower().split()) for b in bullets)]
    problems = []
    if pasted:
        problems.append(
            f"{label}: pastes the resume word for word (\"{min(pasted)}...\"); say it in "
            "your own shorter words, keeping only the key number"
        )
    lowered = paragraph.lower()
    problems += [f"{label}: uses the stock phrase {c!r}; cut it" for c in CLICHES if c in lowered]
    for match in _BRIDGE.finditer(paragraph):
        problems.append(
            f"{label}: explains its own relevance (\"{match.group()[:80]}\"); delete that "
            "sentence and let the achievement speak"
        )
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        named = [s for s in skills if mentions(sentence, s)]
        # "Azure Data Factory" also matches "Azure": count the longest name once.
        named = [n for n in named if not any(n != o and n.lower() in o.lower() for o in named)]
        if len(named) >= STACK_LIMIT:
            problems.append(
                f"{label}: lists {len(named)} tools in one sentence ({', '.join(sorted(named)[:4])}"
                "...); keep the one or two this employer cares about and describe the work"
            )
    return problems


def _role_named(paragraph: str, role_title: str) -> bool:
    """'Data Engineer, Data Management (Hybrid)' is named by 'Data Engineer'."""
    core = re.split(r"\s+[-\u2013\u2014|]\s+|\s*[(,/]", role_title.strip())[0].strip()
    return not core or core.lower() in paragraph.lower()


def _resume_summary(draft: ResumeDraft) -> str:
    lines = [f"OBJECTIVE: {draft.objective}"] if draft.objective else []
    for role in draft.all_roles:
        lines.append(f"\n{role.title}, {role.org} ({role.date_range})")
        lines += [f"  - {b}" for b in role.bullets]
    for project in draft.projects:
        lines.append(f"\nPERSONAL PROJECT {project.name}")
        lines += [f"  - {b}" for b in project.bullets]
    # Without these the letter could not name the degree or the DP-203 it ships with
    # without being flagged for inventing them.
    lines += ["\nSKILLS"] + [f"  {g.label}: {', '.join(g.entries)}" for g in draft.skills]
    lines += ["\nEDUCATION"] + [f"  {e.credential}, {e.institution}" for e in draft.education]
    lines += ["\nCERTIFICATIONS"] + [f"  {c.name} ({c.issuer})" for c in draft.certifications]
    return "\n".join(lines)


def draft_cover(state: GraphState) -> dict:
    master = MasterResume.load(settings.master_resume)
    draft = ResumeDraft.model_validate(state["draft"])

    feedback = ""
    if reviewer := (state.get("cover_feedback") or "").strip():
        feedback = f"\nREVIEWER FEEDBACK ON THE LAST ATTEMPT:\n{reviewer}"

    source = _resume_summary(draft)
    claimable = master.claimable_text()
    domains = unclaimable_domains(state.get("keywords") or [], claimable)
    # Numbers the posting states ("1,600 stores") describe the employer, not the candidate.
    number_source = source + "\n" + " ".join(re.findall(r"\d[\d,.]*", state.get("jd_text") or ""))
    bullets = [b for role in draft.all_roles for b in role.bullets]
    bullets += [b for project in draft.projects for b in project.bullets]
    forbidden = absent_tools(state.get("tools") or [], master.claimable_text())
    skills = master.skill_pool()
    # Checked against the whole resume it accompanies, not bullet by bullet, since a
    # paragraph legitimately draws on several at once. The posting is context: words
    # the employer used are notes, not violations.
    vocabulary = entity_vocabulary(master.skill_pool()) | {
        w.lower() for w in (state.get("company", "") + " " + state.get("role_title", "")).split()
    }
    context = terms(state.get("jd_text", "")) | {
        t for requirement in (state.get("requirements") or []) for t in terms(requirement)
    }

    # One repair round: there is no verify loop after this node, so without it an
    # invented metric or a tool the candidate never used went straight into the PDF.
    base_feedback = feedback
    best = None
    for attempt in range(3):
        body = complete_model(
            get_provider(state.get("llm_provider"), state.get("llm_model")),
            COVER_SYSTEM,
            COVER_USER.format(
                role_title=state.get("role_title", ""),
                company=state.get("company", ""),
                posting=(state.get("jd_text") or "")[:MAX_POSTING_CHARS],
                forbidden=", ".join(forbidden) or "(none)",
                domains=", ".join(domains) or "(none)",
                resume_summary=source,
                feedback=feedback,
            ),
            CoverLetterBody,
            # Warmer on a retry: at 0.4 the repair reproduced the same pasted sentences.
            temperature=0.4 + 0.2 * attempt,
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
        # The one cliche the local model would not drop, even when told three times.
        paragraphs[0] = _OPENER.sub("I am applying for", paragraphs[0])
        body.paragraphs = paragraphs

        violations: list[str] = []
        style: list[str] = []
        notes: list[str] = []
        count = sum(len(p.split()) for p in body.paragraphs)
        if count < MIN_WORDS:
            style.append(f"letter: {count} words leaves half the page empty; expand to "
                         f"{MIN_WORDS + 20}-{MAX_WORDS - 20} words with concrete detail from the "
                         "resume (scale, tools, what changed) -- no filler")
        elif count > MAX_WORDS:
            style.append(f"letter: {count} words runs past one page; cut to under {MAX_WORDS - 20}")
        if not _role_named(body.paragraphs[0], state.get("role_title", "")):
            style.append(f"cover-p1: never names the role; say \"{state.get('role_title')}\" "
                         "in the first sentence")
        for index, paragraph in enumerate(body.paragraphs):
            label = f"cover-p{index + 1}"
            bad, soft = verify_letter(label, number_source, paragraph, vocabulary, context)
            violations += [str(v) for v in bad]
            violations += tool_violations(label, paragraph, forbidden)
            if _YEARS.search(paragraph):
                violations.append(f"{label}: states a years-of-experience figure")
            style += _style_problems(label, paragraph, bullets, skills)
            # A letter legitimately describes the employer's industry ("your financial
            # reporting"), and no word rule tells that from claiming it. So a first-person
            # sentence naming an industry the candidate lacks is a note for the reader,
            # not a reason to regenerate -- as a retry trigger it rejected good letters.
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
                first_person = re.search(r"\b(I|my|me)\b", sentence)
                if first_person and _borrowed_terms("", sentence, claimable):
                    notes.append(f"{label}: check this does not claim industry experience: "
                                 f"\"{sentence[:120]}\"")
            notes += soft
        # Keep the cleanest attempt, not the last: a retry is not always an improvement.
        # Style problems earn a retry but are not claims, so they land in the notes; the
        # red "unverified claims" box stays reserved for something actually invented.
        rank = (len(violations), len(style))
        if best is None or rank < best[0]:
            best = (rank, body, violations, notes + style)
        if not violations and not style:
            break
        # Editing a draft converges; regenerating from a list of complaints just makes
        # different mistakes. So the model gets its own letter back to fix in place.
        feedback = base_feedback + (
            "\n\nYOUR PREVIOUS LETTER (paragraphs separated by blank lines):\n"
            + "\n\n".join(body.paragraphs)
            + "\n\nIt broke these rules. Return the same letter with ONLY the offending "
            "sentences rewritten; keep every other sentence exactly as it is:\n"
            + "\n".join(violations + style)
        )
    _, body, violations, notes = best

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
