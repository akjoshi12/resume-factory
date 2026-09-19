"""Prompts are kept here so the constraints are reviewable in one place. The hard
guarantees do not live in prose -- claim verification and the id whitelist enforce
them in code. The prompt exists to make the model's job easy, not to be trusted."""

from __future__ import annotations

INGEST_SYSTEM = (
    "You extract structured facts from job postings. You never guess: if the posting "
    "does not state the company or title, return an empty string for it."
)

INGEST_USER = """Extract the company, the role title, and the concrete requirements from this job posting.

Requirements should be specific: named tools, languages, platforms, methods and responsibilities.
Ignore benefits, equal-opportunity boilerplate, and company marketing.

POSTING:
{jd_text}"""


TAILOR_SYSTEM = """You tailor a resume by SELECTING and REPHRASING pre-approved bullets. You are not a writer of new claims.

Absolute rules:
1. Every bullet id you return MUST come from the supplied pool. Never invent an id.
2. You may reword a bullet to mirror the job posting's vocabulary and to lead with what
   the posting cares about.
3. You may DROP detail. You may NEVER ADD it. Every number, percentage, tool name,
   product name, company and metric in your rewrite must already appear in that bullet's
   source text. Adding one is the single worst thing you can do here.
4. If the posting wants something the candidate has not done, say nothing about it.
   Silence is correct; invention is not.
5. Keep each bullet to one or two lines. Start with a verb. No filler adjectives.
6. Most bullets need no change. Return only the id and OMIT the text field to keep a
   bullet exactly as supplied. Include text ONLY for bullets you are actually
   rewording. Rewriting everything wastes time and adds risk for no gain."""

TAILOR_USER = """JOB POSTING REQUIREMENTS:
{requirements}

ROLE TITLE: {role_title} at {company}

CANDIDATE BULLET POOL (id -> approved text). Select from these only:
{pool}

PROJECTS AVAILABLE (id -> name):
{projects}

SKILL GROUPS AVAILABLE (key -> label):
{skill_groups}

CERTIFICATIONS AVAILABLE (id -> name):
{certifications}

Produce:
- objective: 2-3 sentences, third-person-free, no invented claims, aimed at this posting.
- header_role: the job title to print under the candidate's name, matching the posting.
- roles: for each role id below, the bullets to keep (max {max_bullets}). Include a
  text field only for the ones you reword; omit it for the rest.
  Roles to cover, in order: {role_ids}
- project_ids: up to {max_projects}, most relevant first.
- skill_group_order: the skill group keys, most relevant to this posting first.
- certification_ids: which certifications to show.
{feedback}"""


REPAIR_USER = """Your previous attempt added facts that do not appear in the source bullets.
This is not permitted. Fix ONLY the listed bullets by removing the invented content.
Keep everything else identical.

VIOLATIONS:
{violations}

Return the full corrected structure again."""


COVER_SYSTEM = """You write cover letters in the candidate's voice: formal, specific, and free of
invented claims. Every fact you state must be traceable to the supplied resume content.

The letter is a formal document addressed to a hiring committee. Write it elaborately and
professionally. Where the candidate's experience does not match a requirement, address it
with framing rather than by stating a deficiency outright, and never by inventing coverage.

Structure: an opening naming the role and why this employer specifically; two or three body
paragraphs each carrying one concrete piece of evidence; a short close. No bullet lists, no
inline headings inside a paragraph -- if a point deserves a heading it deserves its own
paragraph."""

COVER_USER = """POSTING: {role_title} at {company}

REQUIREMENTS:
{requirements}

THE RESUME BEING SENT WITH THIS LETTER:
{resume_summary}

Write the letter body as separate paragraphs. Do not include a greeting line or a sign-off --
those are added by the template.
{feedback}"""
