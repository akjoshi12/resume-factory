"""Measure where generation time actually goes.

    uv run python -m rfactory.bench [track]

Runs the two real calls -- JD ingest and tailoring -- against the configured provider,
once with the reasoning phase disabled and once with it on, and reports elapsed time,
token counts and throughput for each. Reasoning tokens are not in the completion count,
so a large elapsed gap at similar completion counts is the reasoning phase.
"""

from __future__ import annotations

import sys
import time

from rfactory.config import settings
from rfactory.llm.prompts import INGEST_SYSTEM, INGEST_USER, TAILOR_SYSTEM, TAILOR_USER
from rfactory.llm.provider import LLMError, complete_model, get_provider
from rfactory.llm.schemas import JobPosting, Tailoring
from rfactory.models.master import MasterResume

SAMPLE_JD = """Data Quality Analyst, Toronto. You will validate research data pipelines,
investigate data quality issues to root cause, build Power BI reporting for clinical and
operational stakeholders, and write SQL against a hospital data warehouse. Required: 2+
years SQL, experience with data validation and reconciliation, strong communication with
non-technical stakeholders. Nice to have: R, Azure, Databricks."""


def _tailor_prompt(master: MasterResume, track: str) -> str:
    roles = [
        *master.experience_for(track, "professional"),
        *master.experience_for(track, "additional"),
    ]
    return TAILOR_USER.format(
        requirements="- SQL\n- Power BI\n- data validation\n- stakeholder reporting",
        role_title="Data Quality Analyst",
        company="Unity Health",
        pool="\n".join(f"{bid}: {b.text}" for bid, b in master.bullet_pool(track).items()),
        projects="\n".join(f"{p.id}: {p.name}" for p in master.projects_for(track)),
        skill_groups="\n".join(f"{k}: {master.group_label(k)}" for k in master.skills.groups()),
        certifications="\n".join(f"{c.id}: {c.name}" for c in master.certifications_for(track)),
        role_ids=", ".join(r.id for r in roles),
        max_bullets=5,
        max_projects=3,
        feedback="",
    )


def run(label: str, system: str, user: str, schema, max_tokens: int) -> None:  # type: ignore[no-untyped-def]
    provider = get_provider()
    started = time.monotonic()
    try:
        complete_model(provider, system, user, schema, max_tokens=max_tokens, retries=0)
        outcome = "ok"
    except LLMError as exc:
        outcome = f"FAILED ({str(exc)[:60]})"
    total = time.monotonic() - started
    stats = provider.last
    thinking = "off" if settings.disable_thinking else "ON"
    print(
        f"  {label:<8} thinking {thinking:<3} {total:>6.1f}s"
        f"  {stats.prompt_tokens:>5} in {stats.completion_tokens:>5} out"
        f"  {stats.tokens_per_second:>5.1f} tok/s"
        f"{'  TRUNCATED' if stats.truncated else ''}  {outcome}"
    )


def main() -> int:
    track = sys.argv[1] if len(sys.argv) > 1 else "data_analyst"
    master = MasterResume.load(settings.master_resume)
    if track not in master.tracks:
        print(f"unknown track {track!r}; known: {', '.join(master.tracks)}")
        return 2

    from rfactory.llm.provider import active_endpoint

    endpoint = active_endpoint()
    print(f"provider: {endpoint.name}\nmodel:    {endpoint.model} at {endpoint.base_url}")
    print(f"track:    {track}  ({len(master.bullet_pool(track))} bullets in pool)")
    print(f"timeout:  {settings.request_timeout:.0f}s per call\n")

    ingest_user = INGEST_USER.format(jd_text=SAMPLE_JD)
    tailor_user = _tailor_prompt(master, track)

    original = settings.disable_thinking
    try:
        for disabled in (True, False):
            settings.disable_thinking = disabled
            run("ingest", INGEST_SYSTEM, ingest_user, JobPosting, settings.max_tokens_ingest)
            run("tailor", TAILOR_SYSTEM, tailor_user, Tailoring, settings.max_tokens_tailor)
    finally:
        settings.disable_thinking = original

    print(
        "\nA large elapsed gap at similar completion counts is the reasoning phase:\n"
        "those tokens are generated but not reported in 'out'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
