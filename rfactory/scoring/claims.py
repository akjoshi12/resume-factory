"""Claim verification: the rule that makes "select + rephrase" different from
"free generation".

A rephrased bullet may reword, reorder and re-emphasise. It may DROP facts. It may not
ADD them. So every number and every named entity in the rephrased text must already be
present in the master bullet it derives from. This is a deterministic set comparison,
not an LLM judging itself.

It is deliberately noisy in one direction: a false positive costs a retry, a false
negative puts an invented claim on a resume. When the retry budget runs out the
violations are surfaced for a human decision rather than silently accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9.+#/&'-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;:])\s+|\n+")

WORD_NUMBERS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
    "twelve": "12", "dozen": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "hundred": "100", "thousand": "1000", "million": "1000000",
}

# Capitalised words that carry no claim: sentence openers, months, pronouns, connectives.
GENERIC = {
    "a", "an", "the", "and", "or", "but", "if", "as", "at", "by", "for", "from", "in",
    "into", "of", "on", "to", "with", "without", "across", "through", "over", "under",
    "i", "we", "they", "it", "this", "that", "these", "those", "there", "here",
    "led", "built", "designed", "developed", "engineered", "implemented", "applied",
    "worked", "wrote", "ran", "used", "created", "delivered", "defined", "integrated",
    "investigated", "translated", "contributed", "documented", "supervise", "coordinate",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "present",
}


# Category words that describe work rather than assert a fact. Calling a pipeline
# "ELT" is a characterisation; claiming a tool, a metric or a scale is not. Kept
# deliberately short and free of product names -- anything naming a specific
# technology belongs in the master skill pool instead, where it is AJ's own claim.
GENERIC_TECH = {
    "etl", "elt", "api", "apis", "sdk", "ci", "cd", "ci/cd", "ui", "ux", "qa",
    "kpi", "kpis", "sla", "oltp", "olap", "crud", "orm", "e2e", "poc", "mvp",
    "saas", "iac", "nlp", "llm", "llms",
}


@dataclass(slots=True)
class Claims:
    numbers: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)


def _canonical_number(raw: str) -> str:
    cleaned = raw.replace(",", "")
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".") or "0"
    else:
        cleaned = cleaned.lstrip("0") or "0"
    return cleaned


def extract_claims(text: str) -> Claims:
    claims = Claims()

    for match in _NUMBER.finditer(text):
        claims.numbers.add(_canonical_number(match.group()))

    for sentence in _SENTENCE_SPLIT.split(text):
        tokens = list(_TOKEN.finditer(sentence))
        for index, match in enumerate(tokens):
            token = match.group()
            lowered = token.lower().strip(".-'")
            if not lowered:
                continue
            if lowered in WORD_NUMBERS:
                claims.numbers.add(WORD_NUMBERS[lowered])
                continue
            if lowered in GENERIC:
                continue
            has_inner_caps = any(c.isupper() for c in token[1:])
            is_acronym = token.isupper() and len(token) > 1
            has_digits = any(c.isdigit() for c in token)
            is_capitalised = token[0].isupper() and index > 0
            if has_inner_caps or is_acronym or has_digits or is_capitalised:
                claims.entities.add(lowered)

    return claims


@dataclass(slots=True)
class Violation:
    bullet_id: str
    kind: str  # "number" | "entity"
    value: str

    def __str__(self) -> str:
        return f"{self.bullet_id}: invented {self.kind} {self.value!r}"


def verify_bullet(
    bullet_id: str,
    source: str,
    rephrased: str,
    allowed_entities: set[str] | None = None,
) -> list[Violation]:
    """Facts present in the rephrased text but absent from its source bullet.

    Numbers are checked strictly against the source bullet -- a metric is the thing
    most worth not inventing. Entities may additionally come from allowed_entities
    (pass the master skill pool) or GENERIC_TECH, since naming a technology AJ has
    declared is not a fabrication."""
    src = extract_claims(source)
    out = extract_claims(rephrased)
    permitted = src.entities | GENERIC_TECH | {e.lower() for e in (allowed_entities or set())}
    violations = [
        Violation(bullet_id, "number", value) for value in sorted(out.numbers - src.numbers)
    ]
    violations += [
        Violation(bullet_id, "entity", value) for value in sorted(out.entities - permitted)
    ]
    return violations


def entity_vocabulary(skills: set[str]) -> set[str]:
    """Split multi-word skill names into the tokens the checker compares against."""
    vocabulary: set[str] = set()
    for skill in skills:
        for token in _TOKEN.finditer(skill):
            vocabulary.add(token.group().lower().strip(".-'"))
    return vocabulary


def verify_pairs(
    pairs: list[tuple[str, str, str]], allowed_entities: set[str] | None = None
) -> list[Violation]:
    """pairs of (bullet_id, source_text, rephrased_text)."""
    return [v for bid, src, out in pairs for v in verify_bullet(bid, src, out, allowed_entities)]


def verify_letter(
    paragraph_id: str,
    source: str,
    text: str,
    allowed_entities: set[str] | None = None,
    context_entities: set[str] | None = None,
) -> tuple[list[Violation], list[str]]:
    """Cover letters need a different rule from bullets.

    A bullet is a claim, so every fact in it must trace to its source. A letter is
    addressed TO someone: it legitimately names the employer, the role title, and the
    technologies the posting asks for -- including to say the candidate has not used
    them. Judging a letter by the bullet rule flags "my exposure is stronger on Azure
    than on Kubernetes" as inventing Kubernetes, which is the opposite of what the
    sentence does.

    So: numbers stay strict against the resume, because an invented metric is the real
    danger and no posting can license one. Entities drawn from the posting become a
    note rather than a violation -- the checker cannot tell claiming from disclaiming,
    so it surfaces the sentence for a human instead of pretending to judge it.
    """
    src = extract_claims(source)
    out = extract_claims(text)
    permitted = src.entities | GENERIC_TECH | {e.lower() for e in (allowed_entities or set())}
    context = {e.lower() for e in (context_entities or set())}

    violations = [
        Violation(paragraph_id, "number", value) for value in sorted(out.numbers - src.numbers)
    ]
    notes: list[str] = []
    for entity in sorted(out.entities - permitted):
        if entity in context:
            notes.append(
                f"{paragraph_id}: mentions '{entity}' from the posting, which is not on your "
                "resume - check the sentence does not imply experience you do not have"
            )
        else:
            violations.append(Violation(paragraph_id, "entity", entity))
    return violations, notes
