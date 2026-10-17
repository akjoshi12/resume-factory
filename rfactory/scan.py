"""Quick scan: should this posting get an application at all?

One model call reads the posting and judges fit; the deterministic checks beside it
(named tools found in the master resume, requirement keywords the master can cover,
years asked versus years held) keep the number from resting on the model's opinion.
"""

from __future__ import annotations

from datetime import date

from rfactory.config import settings
from rfactory.llm.prompts import SCAN_SYSTEM, SCAN_USER
from rfactory.llm.provider import complete_model, get_provider
from rfactory.llm.schemas import FitScan
from rfactory.models.master import MasterResume
from rfactory.scoring import ats
from rfactory.scoring.claims import absent_tools
from rfactory.scoring.coverage import score as coverage

MAX_JD_CHARS = 12000


def _months(start: str, end: str | None) -> int:
    y1, m1 = map(int, start.split("-")[:2])
    y2, m2 = map(int, end.split("-")[:2]) if end else (date.today().year, date.today().month)
    return max(0, (y2 - y1) * 12 + m2 - m1)


def years_of_experience(master: MasterResume) -> float:
    months = sum(_months(e.start, e.end) for e in master.experience if e.section == "professional")
    return round(months / 12, 1)


def _candidate(master: MasterResume) -> str:
    lines = []
    for e in master.experience:
        lines.append(f"{e.title}, {e.org} ({e.date_range.replace('--', '-')})")
        lines += [f"  - {b.text}" for b in e.bullets]
    for p in master.projects:
        lines.append(f"Personal project: {p.name}")
        lines += [f"  - {b.text}" for b in p.bullets]
    for key, entries in master.skills.groups().items():
        lines.append(f"{master.group_label(key)}: {', '.join(entries)}")
    lines += [f"Education: {e.credential}, {e.institution}" for e in master.education]
    lines += [f"Certification: {c.name}" for c in master.certifications]
    return "\n".join(lines)


def verdict(match: int) -> str:
    return "Apply" if match >= 70 else "Stretch - apply if keen" if match >= 50 else "Skip"


def quick_scan(jd_text: str, provider: str = "", model: str = "") -> dict:
    master = MasterResume.load(settings.master_resume)
    years = years_of_experience(master)
    result = complete_model(
        get_provider(provider or None, model or None),
        SCAN_SYSTEM,
        SCAN_USER.format(jd_text=jd_text[:MAX_JD_CHARS], years=years, candidate=_candidate(master)),
        FitScan,
        temperature=0.2,
        max_tokens=settings.max_tokens_cover,
        acceptable=lambda s: bool(s.requirements),
    )

    claimable = master.claimable_text()
    missing = absent_tools(result.tools, claimable)
    tools = list(dict.fromkeys(t.strip() for t in result.tools if t.strip()))
    have = [t for t in tools if t not in missing]
    tool_ratio = len(have) / len(tools) if tools else 1.0
    keyword_ceiling = coverage("", claimable, focus=result.requirements).score
    deterministic = 100 * (0.6 * tool_ratio + 0.4 * keyword_ceiling)

    gaps = list(result.gaps)
    if result.required_years and result.required_years > years + 1:
        deterministic -= 15
        if not any("year" in g.lower() for g in gaps):
            gaps.insert(0, f"asks for {result.required_years}+ years; you have about {years}")

    match = round(0.5 * max(0, min(100, result.score)) + 0.5 * max(0.0, deterministic))
    return {
        "company": result.company,
        "role_title": result.role_title,
        "match": match,
        "verdict": verdict(match),
        "reason": result.reason,
        "strengths": result.strengths[:4],
        "gaps": gaps[:5],
        "tools_have": have,
        "tools_missing": missing,
        "model_score": result.score,
        "keyword_ceiling": round(keyword_ceiling * 100),
        # Same formula the review page uses after generation, over everything you could
        # truthfully put on the page: the generated resume's ATS score lands at or below it.
        "ats_ceiling": ats.estimate(
            f"{result.role_title}\n{claimable}",
            requirements=result.requirements,
            tools=result.tools,
            phrases=result.keywords,
            role_title=result.role_title,
        )["score"],
    }
