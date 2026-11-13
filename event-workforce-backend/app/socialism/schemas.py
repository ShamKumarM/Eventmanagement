from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkerFollowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_id: UUID


class ChatMessageCreate(BaseModel):
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
