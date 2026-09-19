"""JD keyword coverage: which terms the job description asks for actually appear on
the resume. A defensible, checkable number -- not an 'ATS score'."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")

STOPWORDS = {
    "a", "about", "above", "all", "also", "an", "and", "any", "are", "as", "at", "be",
    "been", "being", "both", "but", "by", "can", "could", "do", "does", "each", "for",
    "from", "has", "have", "how", "if", "in", "into", "is", "it", "its", "may", "more",
    "most", "must", "not", "of", "on", "or", "other", "our", "out", "over", "should",
    "so", "some", "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "to", "up", "use", "using", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "will",
    "with", "within", "would", "you", "your", "work", "working", "team", "teams",
    "role", "roles", "experience", "years", "year", "ability", "strong", "good",
    "excellent", "including", "etc", "new", "well", "help", "make", "across", "plus",
}


def terms(text: str, *, min_length: int = 3) -> set[str]:
    return {
        token.group().lower().strip(".-")
        for token in _TOKEN.finditer(text)
        if len(token.group()) >= min_length and token.group().lower() not in STOPWORDS
    }


@dataclass(slots=True)
class CoverageReport:
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def summary(self) -> str:
        total = len(self.matched) + len(self.missing)
        return f"{len(self.matched)}/{total} JD terms present ({self.score:.0%})"


def score(jd_text: str, resume_text: str, *, focus: list[str] | None = None) -> CoverageReport:
    """focus narrows scoring to requirement phrases pulled out of the JD; without it,
    every non-stopword term in the JD counts, which is noisier but needs no model."""
    wanted = {t for phrase in focus for t in terms(phrase)} if focus else terms(jd_text)
    if not wanted:
        return CoverageReport()
    have = terms(resume_text)
    matched = sorted(wanted & have)
    missing = sorted(wanted - have)
    return CoverageReport(matched=matched, missing=missing, score=len(matched) / len(wanted))
