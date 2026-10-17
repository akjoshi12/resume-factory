"""An ATS-style match estimate, in the shape commercial resume scanners report it.

No applicant tracking system emits a score, so this is a proxy with its weights in
plain sight: named tools (hard skills) matter most, then requirement keywords, then
whether the job title appears, then whether the PDF parses cleanly.
"""

from __future__ import annotations

import re

from rfactory.scoring.claims import mentions
from rfactory.scoring.coverage import keywords, score

WEIGHTS = {"tools": 0.45, "keywords": 0.35, "title": 0.10, "format": 0.10}


def phrases_found(phrases: list[str], text: str) -> list[str]:
    """A phrase counts when all its content words are present (stemmed), so 'root-cause
    analysis' meets 'root cause ... analysis' -- closer to how ATS search behaves than
    scoring every word of every requirement sentence."""
    have = keywords(text)
    return [p for p in phrases if (words := keywords(p)) and words <= have or mentions(text, p)]


def _phrase_score(phrases: list[str], text: str) -> float:
    phrases = list(dict.fromkeys(p.strip() for p in phrases if p.strip()))
    return len(phrases_found(phrases, text)) / len(phrases) if phrases else 0.0


def estimate(
    resume_text: str,
    *,
    requirements: list[str],
    tools: list[str],
    phrases: list[str] | None = None,
    role_title: str = "",
    parses: bool = True,
) -> dict:
    tools = list(dict.fromkeys(t.strip() for t in tools if t.strip()))
    found = [t for t in tools if mentions(resume_text, t)]
    # "Data Engineer, Enterprise Data, Insights & Analytics": the title is the part
    # before the comma; the rest names the team.
    title_words = keywords(re.split(r"[,(|]| - ", role_title)[0])
    title_hit = len(title_words & keywords(resume_text)) / len(title_words) if title_words else None
    parts = {
        "tools": len(found) / len(tools) if tools else None,
        "keywords": _phrase_score(phrases, resume_text) if phrases
        else score("", resume_text, focus=requirements).score if requirements else None,
        "title": title_hit,
        "format": 1.0 if parses else 0.0,
    }
    # A part the posting gives nothing to measure (no named tools, say) drops out and
    # the rest are reweighted, rather than scoring it as a zero or a free pass.
    live = {k: v for k, v in parts.items() if v is not None}
    total = sum(WEIGHTS[k] for k in live)
    value = sum(WEIGHTS[k] * v for k, v in live.items()) / total
    found_phrases = phrases_found(phrases or [], resume_text)
    return {
        "score": round(value * 100),
        "parts": {k: round(v * 100) for k, v in live.items()},
        "tools_found": found,
        "tools_missing": [t for t in tools if t not in found],
        "phrases_missing": [p for p in (phrases or []) if p not in found_phrases],
    }
