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
_FIRST_PERSON = re.compile(r"\b(?:I|my|me|I'm|I've|I'd)\b")

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
        # "Azure-based" and "ETL/ELT" are judged part by part: each half is a known
        # word, but the joined token is in no vocabulary and read as an invention.
        words = [
            (index, part)
            for index, match in enumerate(tokens)
            for part in (re.split(r"[-/]", match.group()) or [match.group()])
            if part
        ]
        for index, token in words:
            # "Docebo's" is the employer the letter is addressed to, not a new name.
            lowered = token.lower().replace("\u2019", "'").removesuffix("'s").strip(".-'")
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


def dropped_keywords(
    bullet_id: str, source: str, rephrased: str, keywords: set[str]
) -> list[str]:
    """Numbers and named skills the source had and the rewrite lost. Tailoring that
    deletes 'Jenkins' and '200GB' to look tidy scores worse than the original."""
    src, out = extract_claims(source), extract_claims(rephrased)
    lost = sorted(src.numbers - out.numbers)
    lost += sorted(e for e in src.entities - out.entities if e in keywords)
    return [f"{bullet_id}: dropped {value!r} from the source; keep it" for value in lost]


def entity_vocabulary(skills: set[str]) -> set[str]:
    """Split multi-word skill names into the tokens the checker compares against."""
    vocabulary: set[str] = set()
    for skill in with_aliases("\n".join(skills)).splitlines():
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
    # "Zurich's Data Management team builds..." describes the employer; only a sentence
    # in the candidate's own voice can claim a posting term. Noting the rest was noise.
    claimed = extract_claims(" ".join(
        s for s in _SENTENCE_SPLIT.split(text) if _FIRST_PERSON.search(s)
    )).entities

    violations = [
        Violation(paragraph_id, "number", value) for value in sorted(out.numbers - src.numbers)
    ]
    notes: list[str] = []
    for entity in sorted(out.entities - permitted):
        if entity in context:
            if entity not in claimed:
                continue
            notes.append(
                f"{paragraph_id}: mentions '{entity}' from the posting, which is not on your "
                "resume - check the sentence does not imply experience you do not have"
            )
        else:
            violations.append(Violation(paragraph_id, "entity", entity))
    return violations, notes


# Same tool, other name. ponytail: hand-kept; add a pair when a real miss shows up.
ALIASES = {"spark": ["PySpark"], "apache spark": ["PySpark"], "ms excel": ["Excel"]}

def with_aliases(text: str) -> str:
    """The text plus every alias name it implies: material that says PySpark may say Spark."""
    implied = [name for name, alts in ALIASES.items() if any(mentions(text, a) for a in alts)]
    return "\n".join([text, *implied])


# A posting's "Azure Databricks" is the resume's "Databricks".
VENDORS = {"azure", "microsoft", "ms", "google", "gcp", "aws", "amazon", "apache"}
# ...but "Google Cloud" is not "Cloud", nor "Azure SQL" plain SQL. ponytail: a short
# deny-list, not a product catalogue; extend it when a new false match shows up.
GENERIC_PRODUCT = {"cloud", "sql", "functions", "storage", "web services", "search", "ml", "ai"}


def mentions(text: str, name: str) -> bool:
    """Case-insensitive whole-word match, so 'Git' does not hit 'GitHub' and lowercase
    tools like 'dbt' are seen -- the entity extractor only notices capitalised ones.
    A plural counts ('CSVs' for 'CSV'), and so does the name without a vendor prefix."""
    words = name.strip().split()
    names = [name.strip(), *ALIASES.get(name.strip().lower(), [])]
    rest = " ".join(words[1:])
    if len(words) > 1 and words[0].lower() in VENDORS and rest.lower() not in GENERIC_PRODUCT:
        names.append(rest)
    return any(
        re.search(rf"(?<![\w-]){re.escape(n)}s?(?![\w-])", text, re.IGNORECASE) is not None
        for n in names
    )


def absent_tools(tools: list[str], claimable: str) -> list[str]:
    """Posting tools that appear nowhere in the candidate's material."""
    return [t for t in dict.fromkeys(t.strip() for t in tools) if t and not mentions(claimable, t)]


def tool_violations(label: str, text: str, absent: list[str]) -> list[str]:
    return [
        f"{label}: mentions {tool!r}, which the candidate has never used; remove it"
        for tool in absent
        if mentions(text, tool)
    ]
