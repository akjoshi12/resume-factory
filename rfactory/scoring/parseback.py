"""Can a real parser get the facts back out of our own PDF?

This is the closest honest proxy for ATS behaviour. It is NOT an "ATS score" -- no
applicant tracking system returns one. It answers a narrower, checkable question:
if a text extractor reads this file, do the name, employers, dates and schools
survive as readable text?

Two extractors are used because they disagree. pdfplumber splits words by horizontal
gap; at its default x_tolerance of 3 the tight glyph advances in Source Sans Pro make
it run words together ("AzureDataFactory"). pdftotext uses the PDF's own text
operators and does not. A resume that only survives the lenient extractor is not
broken, but it has less margin than one that survives both.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rfactory.models.draft import ResumeDraft

_WS = re.compile(r"\s+")
_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-"})

# pdfplumber's default (3) is deliberately included: it is the sloppy-parser case.
STRICT_TOLERANCE = 1.5
LENIENT_TOLERANCE = 3.0


def _norm(text: str) -> str:
    return _WS.sub(" ", text.translate(_DASHES).replace("---", "-").replace("--", "-")).strip().lower()


def extract_pdfplumber(pdf: bytes, x_tolerance: float = STRICT_TOLERANCE) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return "\n".join(page.extract_text(x_tolerance=x_tolerance) or "" for page in doc.pages)


def extract_pdftotext(pdf: bytes) -> str | None:
    """None when poppler is not installed -- absence is not a failure."""
    binary = shutil.which("pdftotext")
    if binary is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.pdf"
        path.write_bytes(pdf)
        proc = subprocess.run(
            [binary, "-layout", str(path), "-"], capture_output=True, text=True, timeout=60
        )
        return proc.stdout if proc.returncode == 0 else None


def extract_text(pdf: bytes) -> str:
    return extract_pdfplumber(pdf)


@dataclass(slots=True)
class ParseReport:
    missing: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)
    by_extractor: dict[str, list[str]] = field(default_factory=dict)
    spacing_risk: bool = False
    text: str = ""

    @property
    def ok(self) -> bool:
        return not self.missing


def expectations_from_draft(draft: "ResumeDraft") -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = [
        ("name", draft.profile.name),
        ("email", draft.profile.email),
    ]
    for role in draft.all_roles:
        items.append((f"org:{role.id}", role.org))
        items.append((f"dates:{role.id}", role.date_range))
    for item in draft.education:
        items.append((f"edu:{item.institution}", item.institution))
    items += [("section:skills", "skills"), ("section:education", "education")]
    return items


def check_expectations(pdf: bytes, expectations: list[tuple[str, str]]) -> ParseReport:
    texts: dict[str, str] = {"pdfplumber": extract_pdfplumber(pdf)}
    if (popplered := extract_pdftotext(pdf)) is not None:
        texts["pdftotext"] = popplered

    report = ParseReport(text=texts["pdfplumber"])
    haystacks = {name: _norm(raw) for name, raw in texts.items()}

    for name, hay in haystacks.items():
        report.by_extractor[name] = [
            label for label, needle in expectations if _norm(needle) not in hay
        ]

    # A fact counts as recoverable if any extractor finds it.
    for label, needle in expectations:
        probe = _norm(needle)
        if any(probe in hay for hay in haystacks.values()):
            report.found.append(label)
        else:
            report.missing.append(label)

    lenient = _norm(extract_pdfplumber(pdf, LENIENT_TOLERANCE))
    report.spacing_risk = any(_norm(n) not in lenient for _, n in expectations)
    return report


def check(pdf: bytes, draft: "ResumeDraft") -> ParseReport:
    return check_expectations(pdf, expectations_from_draft(draft))
