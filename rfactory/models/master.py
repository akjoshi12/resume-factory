from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

_MONTHS = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}


def fmt_month(value: str | None) -> str:
    """'2022-07' -> 'Jul 2022'. Empty or None -> 'Present'."""
    if not value:
        return "Present"
    year, _, month = value.partition("-")
    return f"{_MONTHS.get(month, month)} {year}" if month else year


class Profile(BaseModel):
    """Permanent identity block. Never edited per application, never sent to the model."""

    name: str
    phone: str = ""
    email: str
    location: str = ""
    role_default: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio_url: str = ""
    portfolio_name: str = ""


class Bullet(BaseModel):
    id: str
    priority: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    text: str
    # Hand-written alternate phrasings of the same fact, each aimed at a different kind
    # of posting. Approved like `text`, so the app may swap one in without checking it.
    variants: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    id: str
    org: str
    title: str
    location: str = ""
    start: str
    end: str | None = None
    section: str = "professional"  # "professional" | "additional"
    tracks: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)

    @property
    def date_range(self) -> str:
        return f"{fmt_month(self.start)} -- {fmt_month(self.end)}"


class Project(BaseModel):
    id: str
    name: str
    subtitle: str = ""
    status: str = ""
    stack: list[str] = Field(default_factory=list)
    tracks: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)


class Education(BaseModel):
    id: str
    institution: str
    credential: str
    location: str = ""
    start: str
    end: str | None = None

    @property
    def date_range(self) -> str:
        return f"{fmt_month(self.start)} - {fmt_month(self.end)}"


class Certification(BaseModel):
    id: str
    name: str
    issuer: str = ""
    tracks: list[str] = Field(default_factory=list)


class Activity(BaseModel):
    id: str
    title: str
    dates: str = ""
    tracks: list[str] = Field(default_factory=list)


class StaleSkills(BaseModel):
    note: str = ""
    items: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Groups are open-ended; every non-'stale' list key is a group of skill strings."""

    model_config = ConfigDict(extra="allow")

    stale: StaleSkills = Field(default_factory=StaleSkills)

    def groups(self) -> dict[str, list[str]]:
        extra = self.__pydantic_extra__ or {}
        return {k: v for k, v in extra.items() if isinstance(v, list)}

    def is_stale(self, skill: str) -> bool:
        return skill in self.stale.items


class MasterResume(BaseModel):
    schema_version: str
    updated: str = ""
    tracks: list[str] = Field(default_factory=list)
    profile: Profile
    skill_group_labels: dict[str, str] = Field(default_factory=dict)
    # Hand-written per-track summaries, used when the model's objective fails checks.
    objectives: dict[str, str] = Field(default_factory=dict)
    # skill entry -> other names for the same skill ("ETL/ELT Pipelines" -> "Data
    # Ingestion"). Printed beside the entry only when the posting uses that name.
    skill_aliases: dict[str, list[str]] = Field(default_factory=dict)
    skills: Skills
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> MasterResume:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    # -- track-filtered views -------------------------------------------------

    def experience_for(self, track: str, section: str = "professional") -> list[Experience]:
        """EVERY role in the section, whatever the track. Dropping a role leaves an
        unexplained gap in the timeline, which costs more than an off-target role does.
        Tracks only influence which bullets are chosen and in what order, never whether
        a role appears. `track` is kept in the signature for callers."""
        hits = [e for e in self.experience if e.section == section]
        return sorted(hits, key=lambda e: e.end or "9999-99", reverse=True)

    def role_bullets(self, track: str) -> dict[str, dict[str, Bullet]]:
        """role id -> {bullet id -> bullet}. A bullet may only ever be printed under
        the role it belongs to; this is the map that enforces it."""
        return {
            e.id: {b.id: b for b in e.bullets}
            for section in ("professional", "additional")
            for e in self.experience_for(track, section)
        }

    def projects_for(self, track: str) -> list[Project]:
        return [p for p in self.projects if track in p.tracks]

    def certifications_for(self, track: str) -> list[Certification]:
        return [c for c in self.certifications if track in c.tracks]

    def activities_for(self, track: str) -> list[Activity]:
        return [a for a in self.activities if track in a.tracks]

    def group_label(self, key: str) -> str:
        return self.skill_group_labels.get(key, key.replace("_", " ").title())

    def bullet_pool(self, track: str) -> dict[str, Bullet]:
        """Every bullet id the model is allowed to reference for this track.
        Anything outside this mapping is, by definition, invented."""
        pool: dict[str, Bullet] = {}
        for section in ("professional", "additional"):
            for e in self.experience_for(track, section):
                pool.update({b.id: b for b in e.bullets})
        for p in self.projects_for(track):
            pool.update({b.id: b for b in p.bullets})
        return pool

    def claimable_text(self) -> str:
        """Everything the candidate can stand behind, as one string: the universe a
        tool name must appear in before any generated text may mention it."""
        parts = [
            t for e in self.experience for b in e.bullets for t in (b.text, *b.variants)
        ]
        parts += [a for names in self.skill_aliases.values() for a in names]
        parts += [f"{p.name} {p.subtitle} {' '.join(p.stack)}" for p in self.projects]
        parts += [t for p in self.projects for b in p.bullets for t in (b.text, *b.variants)]
        parts += [s for entries in self.skills.groups().values() for s in entries]
        parts += [f"{c.name} {c.issuer}" for c in self.certifications]
        parts += [f"{e.credential} {e.institution}" for e in self.education]
        from rfactory.scoring.claims import with_aliases

        return with_aliases("\n".join(parts))

    def skill_pool(self) -> set[str]:
        pool = {s for group in self.skills.groups().values() for s in group}
        return pool | {a for s in pool for a in self.skill_aliases.get(s, [])}
