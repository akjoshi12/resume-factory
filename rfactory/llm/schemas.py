from __future__ import annotations

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    company: str = ""
    role_title: str = ""
    requirements: list[str] = Field(
        default_factory=list,
        description="Concrete skills, tools and responsibilities the posting asks for.",
    )
    tools: list[str] = Field(
        default_factory=list,
        description=(
            "Every named technology in the posting: languages, platforms, products, "
            "frameworks, cloud services. Names only, e.g. 'dbt', 'Airflow', 'Snowflake'."
        ),
    )
    keywords: list[str] = Field(
        default_factory=list,
        description=(
            "12-25 short keyword phrases (1-3 words) a recruiter would search an ATS for: "
            "skills, methods, domain terms, e.g. 'data reconciliation', 'root cause "
            "analysis', 'KPI', 'UAT'. Include the named tools too."
        ),
    )


class TailoredBullet(BaseModel):
    id: str = Field(description="Must be an id from the supplied bullet pool.")
    text: str = Field(
        default="",
        description=(
            "The bullet rewritten in the posting's vocabulary, same facts. Empty string "
            "keeps the approved text unchanged."
        ),
    )


class TailoredRole(BaseModel):
    id: str
    bullets: list[TailoredBullet] = Field(default_factory=list)


class Tailoring(BaseModel):
    objective: str = ""
    header_role: str = Field(default="", description="Bare job title to print under the name.")
    roles: list[TailoredRole] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    skill_group_order: list[str] = Field(default_factory=list)
    certification_ids: list[str] = Field(default_factory=list)


class CoverLetterBody(BaseModel):
    recipient: str = "Hiring Manager"
    paragraphs: list[str] = Field(default_factory=list)


class FitScan(BaseModel):
    company: str = ""
    role_title: str = ""
    requirements: list[str] = Field(default_factory=list)
    tools: list[str] = Field(
        default_factory=list, description="Every named technology in the posting, names only."
    )
    keywords: list[str] = Field(
        default_factory=list,
        description=(
            "12-25 short keyword phrases (1-3 words) a recruiter would search an ATS for: "
            "skills, methods, domain terms, e.g. 'data reconciliation', 'root cause "
            "analysis', 'KPI', 'UAT'. Include the named tools too."
        ),
    )
    required_years: int = Field(
        default=0, description="Minimum years of experience the posting asks for; 0 if unstated."
    )
    score: int = Field(default=0, description="0-100: how well the candidate fits this posting.")
    strengths: list[str] = Field(default_factory=list, description="Up to 4 concrete matches.")
    gaps: list[str] = Field(default_factory=list, description="Up to 4 real gaps, most serious first.")
    reason: str = Field(default="", description="Two sentences: should they apply, and why.")
