from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FriendRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_id: UUID


class FriendRequestAction(str, Enum):
    accept = "accept"
    reject = "reject"
    cancel = "cancel"


class FriendRequestRespond(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: FriendRequestAction


class ChatMessageCreate(BaseModel):
    """Send either a text message or a job card, never both."""

    model_config = ConfigDict(extra="forbid")
    body: str | None = Field(default=None, min_length=1, max_length=4000)
    job_id: UUID | None = None

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def exactly_one_message_kind(self):
        if (self.body is None) == (self.job_id is None):
            raise ValueError("Provide either a message body or a job_id.")
        return self
