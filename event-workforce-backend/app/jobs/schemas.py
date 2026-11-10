from datetime import date, datetime, timezone , timedelta, time
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(IST).date()


class PaymentType(str, Enum):
    spot_pay = "spot_pay"
    two_days = "two_days"
    custom_days = "custom_days"
    other = "other"


class JobStatus(str, Enum):
    draft = "draft"
    open = "open"
    filled = "filled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"


class TimeOfDay(str, Enum):
    morning = "morning"      # 05:00-12:00
    afternoon = "afternoon"  # 12:00-16:00
    evening = "evening"      # 16:00-21:00
    night = "night"          # 21:00-05:00


class JobBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=150)
    category_id: int
    category_other: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=2000)

    job_date: date
    reporting_time: time
    start_time: time
    end_time: Optional[time] = None

    workers_required: int = Field(ge=1, le=1000)
    salary_per_worker: float = Field(gt=0, le=100000)
    payment_type: PaymentType
    payment_days: Optional[int] = Field(default=None, ge=1, le=60)
    payment_note: Optional[str] = Field(default=None, max_length=200)

    # Location is selected hierarchically in the app; coordinates stay backend-managed.
    state: str = Field(min_length=2, max_length=80)
    district: str = Field(min_length=2, max_length=100)
    area: str = Field(min_length=2, max_length=120)
    venue_name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=10, max_length=500)
    maps_url: Optional[str] = Field(default=None, max_length=500)

    food_provided: bool = False
    transport_provided: bool = False
    dress_code: Optional[str] = Field(default=None, max_length=200)

    @field_validator("title", "state", "district", "area", "venue_name", "address")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Please enter this information.")
        return cleaned

    @field_validator("category_other", "description", "payment_note", "maps_url", "dress_code")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


JOB_FIELDS = list(JobBase.model_fields)


class JobCreate(JobBase):
    @field_validator("job_date")
    @classmethod
    def date_not_in_past(cls, v: date) -> date:
        if v < today_ist():
            raise ValueError("Choose today or a future date.")
        return v

    @model_validator(mode="after")
    def cross_checks(self):
        # end_time <= start_time is allowed (event runs past midnight).
        if self.reporting_time > self.start_time:
            raise ValueError("Reporting time must be the same as or earlier than the start time.")
        if self.payment_type == PaymentType.custom_days and not self.payment_days:
            raise ValueError("Enter the number of days when you choose custom payment.")
        return self


class JobUpdate(BaseModel):
    """All fields optional; the merged result is re-validated as JobCreate."""
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = None
    category_id: Optional[int] = None
    category_other: Optional[str] = None
    description: Optional[str] = None
    job_date: Optional[date] = None
    reporting_time: Optional[time] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    workers_required: Optional[int] = None
    salary_per_worker: Optional[float] = None
    payment_type: Optional[PaymentType] = None
    payment_days: Optional[int] = None
    payment_note: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    area: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    maps_url: Optional[str] = None
    food_provided: Optional[bool] = None
    transport_provided: Optional[bool] = None
    dress_code: Optional[str] = None
