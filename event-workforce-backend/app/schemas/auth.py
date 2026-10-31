
import re
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator


Password = Annotated[
    str,
    StringConstraints(min_length=8, max_length=128),
]


def validate_password_strength(password: str) -> str:
    requirements = {
        "uppercase letter": r"[A-Z]",
        "lowercase letter": r"[a-z]",
        "number": r"\d",
        "special symbol": r"[^A-Za-z0-9]",
    }

    missing = [
        name
        for name, pattern in requirements.items()
        if not re.search(pattern, password)
    ]

    if missing:
        raise ValueError(
            "Password must contain at least one "
            + ", one ".join(missing)
            + "."
        )

    return password


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: Password

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class CompletePasswordResetRequest(BaseModel):
    access_token: str = Field(min_length=1)
    refresh_token: str = Field(min_length=1)
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
