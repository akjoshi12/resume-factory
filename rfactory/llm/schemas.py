from __future__ import annotations

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    company: str = ""
    role_title: str = ""
    requirements: list[str] = Field(
        default_factory=list,
        description="Concrete skills, tools and responsibilities the posting asks for.",
    )


class TailoredBullet(BaseModel):
    id: str = Field(description="Must be an id from the supplied bullet pool.")
    text: str = Field(
        default="",
        description=(
            "ONLY when you are changing the wording. Omit it to keep the approved "
            "bullet exactly as supplied."
        ),
    )


class TailoredRole(BaseModel):
    id: str
    bullets: list[TailoredBullet] = Field(default_factory=list)


class Tailoring(BaseModel):
    objective: str = ""
    header_role: str = Field(default="", description="Job title to print under the name.")
    roles: list[TailoredRole] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    skill_group_order: list[str] = Field(default_factory=list)
    certification_ids: list[str] = Field(default_factory=list)


class CoverLetterBody(BaseModel):
    recipient: str = "Hiring Manager"
    paragraphs: list[str] = Field(default_factory=list)
