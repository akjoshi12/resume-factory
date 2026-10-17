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

# Words a posting uses to describe the candidate rather than the work. Counting them
# made "exceptional", "comfort" and "similar" a third of the denominator, so a resume
# that hit every tool and practice still read as 40%.
SOFT = {
    "like", "similar", "related", "equivalent", "practical", "exceptional", "comfort",
    "familiarity", "foundational", "understanding", "hands-on", "hands", "ensure",
    "field", "degree", "bachelor", "master", "deep", "solid", "proven", "ideal",
    "preferred", "required", "requirement", "asset", "nice", "have", "bring", "seeking",
    "looking", "join", "able", "knowledge", "skill", "skills", "background", "level",
    "early", "career", "momentum", "relentless", "dedication", "rigor", "superpower",
    "world-class", "innovative", "seamless", "vital", "pristine", "clear", "clean",
    "high", "highly", "relevant", "various", "multiple", "environment", "environments",
    "concept", "concepts", "navigating", "guided", "supervision", "day", "daily",
    "deliver", "create", "write", "build", "implement", "maintain", "execute", "support",
    "perform", "develop", "drive", "own", "use", "need", "needs", "set", "based",
    "least", "minimum", "one", "two", "three", "time", "best", "real", "world",
}


def terms(text: str, *, min_length: int = 3) -> set[str]:
    return {
        token.group().lower().strip(".-")
        for token in _TOKEN.finditer(text)
        if len(token.group()) >= min_length and token.group().lower() not in STOPWORDS
    }


def _stem(word: str) -> str:
    """Crude on purpose: 'transformations' must meet 'transformation', 'validations'
    'validation', 'pipelines' 'pipeline'. A real stemmer buys little on resume text."""
    for suffix, keep in (("ies", "y"), ("ing", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4 and not word.endswith("ss"):
            return word[: -len(suffix)] + keep
    return word


def keywords(text: str) -> set[str]:
    """Stemmed content terms. Compounds count as their parts too, so 'Git-based' meets
    'Git' and 'ELT/ETL' meets 'ETL'."""
    out: set[str] = set()
    for term in terms(text):
        parts = [p for p in re.split(r"[-/]", term) if p]
        for part in parts if len(parts) > 1 else [term]:
            if len(part) >= 2 and part not in STOPWORDS and part not in SOFT:
                out.add(_stem(part))
    return out


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
    wanted = {t for phrase in focus for t in keywords(phrase)} if focus else keywords(jd_text)
    if not wanted:
        return CoverageReport()
    have = keywords(resume_text)
    matched = sorted(wanted & have)
    missing = sorted(wanted - have)
    return CoverageReport(matched=matched, missing=missing, score=len(matched) / len(wanted))
