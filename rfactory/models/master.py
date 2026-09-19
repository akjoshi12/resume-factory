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
        return f"{fmt_month(self.start)} --- {fmt_month(self.end)}"


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
        hits = [e for e in self.experience if track in e.tracks and e.section == section]
        return sorted(hits, key=lambda e: e.end or "9999-99", reverse=True)

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

    def skill_pool(self) -> set[str]:
        return {s for group in self.skills.groups().values() for s in group}
