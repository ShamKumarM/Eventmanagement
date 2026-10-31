from datetime import date, datetime, timezone , timedelta, time
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

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
    title: str = Field(min_length=3, max_length=150)
    category_id: int
    category_other: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=2000)

    job_date: date
    reporting_time: time
    start_time: time
    end_time: time

    workers_required: int = Field(ge=1, le=1000)
    salary_per_worker: float = Field(gt=0, le=100000)
    payment_type: PaymentType
    payment_days: Optional[int] = Field(default=None, ge=1, le=60)
    payment_note: Optional[str] = Field(default=None, max_length=200)

    venue_name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=3, max_length=300)
    area: str = Field(min_length=2, max_length=80)
    city: str = Field(default="Coimbatore", max_length=80)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    maps_url: Optional[str] = Field(default=None, max_length=500)

    food_provided: bool = False
    transport_provided: bool = False
    dress_code: Optional[str] = Field(default=None, max_length=200)


JOB_FIELDS = list(JobBase.model_fields)


class JobCreate(JobBase):
    @field_validator("job_date")
    @classmethod
    def date_not_in_past(cls, v: date) -> date:
        if v < today_ist():
            raise ValueError("job_date cannot be in the past")
        return v

    @model_validator(mode="after")
    def cross_checks(self):
        # end_time <= start_time is allowed (event runs past midnight).
        if self.reporting_time > self.start_time:
            raise ValueError("reporting_time must be at or before start_time")
        if self.payment_type == PaymentType.custom_days and not self.payment_days:
            raise ValueError("payment_days is required when payment_type is custom_days")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class JobUpdate(BaseModel):
    """All fields optional; the merged result is re-validated as JobCreate."""
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
    venue_name: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    maps_url: Optional[str] = None
    food_provided: Optional[bool] = None
    transport_provided: Optional[bool] = None
    dress_code: Optional[str] = None
