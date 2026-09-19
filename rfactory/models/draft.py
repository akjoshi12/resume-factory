from __future__ import annotations

from pydantic import BaseModel, Field

from rfactory.models.master import Profile


class SkillGroup(BaseModel):
    key: str
    label: str
    # Named "entries", not "items": Jinja resolves .items on a dict to the dict method.
    entries: list[str] = Field(default_factory=list)


class DraftRole(BaseModel):
    """bullet_ids and bullets are parallel: bullets[i] is the text that will be printed,
    bullet_ids[i] names the master bullet it derives from. Claim verification compares
    the two, so the pairing must survive every edit and regeneration."""

    id: str
    org: str
    title: str
    location: str = ""
    date_range: str
    section: str = "professional"
    bullet_ids: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class DraftProject(BaseModel):
    id: str
    name: str
    bullet_ids: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class DraftEducation(BaseModel):
    credential: str
    institution: str
    location: str = ""
    date_range: str


class DraftCertification(BaseModel):
    name: str
    issuer: str = ""


class DraftActivity(BaseModel):
    title: str
    dates: str = ""


class ResumeDraft(BaseModel):
    """The editable object. Profile, education, role titles and date ranges are carried
    here but are never rendered as inputs in the UI."""

    track: str
    profile: Profile
    role: str = ""
    objective: str = ""
    skills: list[SkillGroup] = Field(default_factory=list)
    professional: list[DraftRole] = Field(default_factory=list)
    additional: list[DraftRole] = Field(default_factory=list)
    projects: list[DraftProject] = Field(default_factory=list)
    education: list[DraftEducation] = Field(default_factory=list)
    certifications: list[DraftCertification] = Field(default_factory=list)
    activities: list[DraftActivity] = Field(default_factory=list)

    @property
    def all_roles(self) -> list[DraftRole]:
        return [*self.professional, *self.additional]

    def bullet_count(self) -> int:
        return sum(len(r.bullets) for r in self.all_roles) + sum(
            len(p.bullets) for p in self.projects
        )

    def template_context(self) -> dict[str, object]:
        data = self.model_dump()
        data["skills"] = [g for g in data["skills"] if g["entries"]]
        return data


class CoverLetterDraft(BaseModel):
    profile: Profile
    title: str = ""
    recipient: str = "Hiring Manager"
    greeting: str = "Dear"
    closer: str = "Kind Regards"
    company: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    paragraphs: list[str] = Field(default_factory=list)

    @property
    def phone_plain(self) -> str:
        """main.tex puts this in a tel: href, so strip it to digits and dot-group it."""
        digits = "".join(ch for ch in self.profile.phone if ch.isdigit())
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            return self.profile.phone
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"

    def template_context(self) -> dict[str, object]:
        return {**self.model_dump(), "phone_plain": self.phone_plain}
