from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import ApplicationStatus, EmailCategory, EvidenceLevel


class AIProfileSkill(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    evidence_level: EvidenceLevel = EvidenceLevel.MEDIUM
    evidence_text: str = Field(min_length=1)


class AIProfileProject(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    technologies: list[str] = []
    impact: str | None = None
    evidence_text: str = Field(min_length=1)


class AIProfileExperience(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    start_date: str | None = Field(default=None, max_length=100)
    end_date: str | None = Field(default=None, max_length=100)
    bullets: list[str] = []
    evidence_text: str = Field(min_length=1)


class AIProfileEducation(BaseModel):
    institution: str = Field(min_length=1, max_length=255)
    degree: str = Field(min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=255)
    dates: str | None = Field(default=None, max_length=255)
    evidence_text: str = Field(min_length=1)


class AIProfileCertification(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    issuer: str | None = Field(default=None, max_length=255)
    evidence_text: str = Field(min_length=1)


class AIProfileExtraction(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    communication_style: list[str] = []
    work_preferences: list[str] = []
    skills: list[AIProfileSkill] = []
    projects: list[AIProfileProject] = []
    experiences: list[AIProfileExperience] = []
    education: list[AIProfileEducation] = []
    certifications: list[AIProfileCertification] = []


class AIEmailTriage(BaseModel):
    relevant_to_careerops: bool = True
    category: EmailCategory
    company_name: str | None = Field(default=None, max_length=255)
    role_hint: str | None = Field(default=None, max_length=255)
    status_hint: ApplicationStatus | None = None
    urgency: str = Field(default="normal", max_length=50)
    requires_reply: bool = False
    suggested_action: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class AILinkedInApplicationExtraction(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    role_title: str | None = Field(default=None, max_length=255)
    confidence: int = Field(default=0, ge=0, le=100)
    evidence_span: str | None = Field(default=None, max_length=500)


class AICVExperienceBullet(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    bullet: str = Field(min_length=1)
    why: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class AICVProjectSelection(BaseModel):
    project: str = Field(min_length=1, max_length=255)
    why: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class AICVChange(BaseModel):
    section: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1)


class AICVTailoringPlan(BaseModel):
    summary_focus: list[str] = []
    skills_to_prioritize: list[str] = []
    experience_bullets_to_reuse: list[AICVExperienceBullet] = []
    projects_to_prioritize: list[AICVProjectSelection] = []
    do_not_claim: list[str] = []
    changes: list[AICVChange] = []
