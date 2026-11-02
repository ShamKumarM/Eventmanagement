"""Pydantic schemas for the Applications module."""
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationStatus(str, Enum):
    pending = "pending"
    shortlisted = "shortlisted"
    selected = "selected"
    rejected = "rejected"
    withdrawn = "withdrawn"


# Proposed workflow (confirm with team).
EMPLOYER_TRANSITIONS = {
    ApplicationStatus.pending: {
        ApplicationStatus.shortlisted, ApplicationStatus.selected, ApplicationStatus.rejected,
    },
    ApplicationStatus.shortlisted: {ApplicationStatus.selected, ApplicationStatus.rejected},
}
WORKER_WITHDRAWABLE = {
    ApplicationStatus.pending, ApplicationStatus.shortlisted, ApplicationStatus.selected,
}


class ApplicationCreate(BaseModel):
    # No worker_id field on purpose: the worker is always taken from the token.
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    cover_note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("cover_note")
    @classmethod
    def trim_note(cls, v):
        v = (v or "").strip()
        return v or None


class ApplicationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus