from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContactRequestStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    cancelled = "cancelled"
    revoked = "revoked"


class ContactRequestCreate(BaseModel):
    """The worker asking an employer to share contact details. No ids here: they come from the URL/token."""

    model_config = ConfigDict(extra="forbid")

    message: str | None = Field(default=None, max_length=300)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class ContactRequestRespond(BaseModel):
    """accept/reject answer a pending request; revoke withdraws access that was already accepted."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["accept", "reject", "revoke"]