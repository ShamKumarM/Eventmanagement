"""Profile management endpoints for workers and employers."""
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.deps import get_current_user
from app.auth.db import admin_db

router = APIRouter(prefix="/profile", tags=["Profile Management"])

WORKER_REQUIRED_FIELDS = {
    "full_name": 20,
    "phone": 20,
    "preferred_area": 20,
    "skills": 20,
    "experience_level": 20,
}


def _profile_or_404(user_id: str) -> dict[str, Any]:
    result = (
        admin_db.table("profiles")
        .select("id, full_name, phone, role, role_selected, created_at, updated_at")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return result.data[0]


def _require_role(profile: dict, role: str) -> None:
    if profile.get("role") != role or not profile.get("role_selected"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This endpoint is available only to users who selected the {role} role.",
        )


def _worker_profile(user_id: str) -> dict[str, Any]:
    result = (
        admin_db.table("worker_profiles")
        .select("user_id, bio, preferred_area, preferred_radius_km, is_available, experience_level, created_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        # This should normally be created by the role-selection RPC.
        raise HTTPException(status_code=404, detail="Worker profile not found.")
    return result.data[0]


def _employer_profile(user_id: str) -> dict[str, Any]:
    result = (
        admin_db.table("employer_profiles")
        .select(
            "user_id, organisation_name, description, contact_person, business_area, "
            "verification_status, created_at, business_type, business_address, "
            "years_in_business, website_url, logo_url"
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Employer profile not found.")
    return result.data[0]


def _worker_skill_ids(user_id: str) -> list[int]:
    result = (
        admin_db.table("worker_profile_skills")
        .select("skill_id")
        .eq("user_id", user_id)
        .execute()
    )
    return sorted({int(row["skill_id"]) for row in (result.data or [])})


class SharedProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, min_length=7, max_length=20)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        # Accept international prefixes and common visual separators; normalize
        # to a compact form while keeping a leading plus if supplied.
        compact = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not compact.lstrip("+").isdigit() or compact.count("+") > 1 or ("+" in compact and not compact.startswith("+")):
            raise ValueError("Phone must contain digits and may start with +.")
        if not 7 <= len(compact.lstrip("+")) <= 15:
            raise ValueError("Phone must contain between 7 and 15 digits.")
        return compact


class WorkerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bio: str | None = Field(default=None, max_length=1000)
    preferred_area: str | None = Field(default=None, min_length=2, max_length=120)
    preferred_radius_km: int | None = Field(default=None, ge=1, le=100)
    is_available: bool | None = None
    experience_level: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("bio", "preferred_area", "experience_level")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Value cannot be blank.")
        return cleaned


class SkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_ids: list[int] = Field(min_length=1, max_length=13)

    @field_validator("skill_ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if any(skill_id < 1 for skill_id in value):
            raise ValueError("Skill IDs must be positive integers.")
        if len(value) != len(set(value)):
            raise ValueError("Duplicate skill IDs are not allowed.")
        return value


class EmployerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organisation_name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    contact_person: str | None = Field(default=None, min_length=2, max_length=120)
    business_area: str | None = Field(default=None, min_length=2, max_length=120)
    business_type: str | None = Field(default=None, min_length=2, max_length=100)
    business_address: str | None = Field(default=None, min_length=5, max_length=500)
    years_in_business: int | None = Field(default=None, ge=0, le=200)
    website_url: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "organisation_name", "description", "contact_person", "business_area",
        "business_type", "business_address", "website_url", "logo_url"
    )
    @classmethod
    def trim_employer_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank; use null to clear an optional field.")
        return value

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("website_url must be a complete http:// or https:// URL.")
        return value


@router.get("/me")
def get_my_profile(user=Depends(get_current_user)):
    """Return shared account data and the matching role-specific profile."""
    profile = _profile_or_404(str(user.id))
    response: dict[str, Any] = {
        "id": str(user.id),
        "email": user.email,
        "profile": profile,
    }
    if profile.get("role_selected") and profile.get("role") == "worker":
        response["worker_profile"] = _worker_profile(str(user.id))
        response["skill_ids"] = _worker_skill_ids(str(user.id))
    elif profile.get("role_selected") and profile.get("role") == "employer":
        response["employer_profile"] = _employer_profile(str(user.id))
    return response


@router.patch("/me")
def update_my_shared_profile(payload: SharedProfileUpdate, user=Depends(get_current_user)):
    """Update only shared profile fields; role and role_selected cannot be changed here."""
    profile = _profile_or_404(str(user.id))
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    # Do not permit a caller to set a field to null if it is required by the DB.
    for key, value in patch.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be null.")
    try:
        result = (
            admin_db.table("profiles")
            .update(patch)
            .eq("id", str(user.id))
            .execute()
        )
    except Exception as exc:
        message = str(exc).lower()
        if "duplicate" in message or "unique" in message:
            raise HTTPException(status_code=409, detail="That phone number is already in use.") from exc
        raise HTTPException(status_code=400, detail="Could not update profile. Check supplied values.") from exc
    if not result.data:
        raise HTTPException(status_code=400, detail="Profile update did not return a saved record.")
    return {"message": "Profile updated successfully.", "profile": result.data[0]}


@router.get("/completion")
def worker_profile_completion(user=Depends(get_current_user)):
    """Return worker profile completion and the agreed application eligibility flag."""
    profile = _profile_or_404(str(user.id))
    _require_role(profile, "worker")
    worker = _worker_profile(str(user.id))
    skill_ids = _worker_skill_ids(str(user.id))

    completed = {
        "full_name": bool((profile.get("full_name") or "").strip()),
        "phone": bool((profile.get("phone") or "").strip()),
        "preferred_area": bool((worker.get("preferred_area") or "").strip()),
        "skills": len(skill_ids) > 0,
        "experience_level": bool((worker.get("experience_level") or "").strip()),
    }
    percentage = sum(WORKER_REQUIRED_FIELDS[k] for k, done in completed.items() if done)
    return {
        "completion_percentage": percentage,
        "application_eligible": percentage == 100,
        "required_fields": [
            {"field": key, "weight": weight, "completed": completed[key]}
            for key, weight in WORKER_REQUIRED_FIELDS.items()
        ],
        "missing_fields": [key for key, done in completed.items() if not done],
        "message": (
            "Profile meets the minimum requirements to apply for jobs."
            if percentage == 100
            else "Complete all five required fields before applying for jobs."
        ),
    }


@router.get("/skills")
def list_skills(user=Depends(get_current_user)):
    """List active skills from the existing skills table."""
    _profile_or_404(str(user.id))
    try:
        result = admin_db.table("skills").select("id, name").order("id").execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not load skills.") from exc
    return result.data or []


@router.get("/worker")
def get_worker_profile(user=Depends(get_current_user)):
    profile = _profile_or_404(str(user.id))
    _require_role(profile, "worker")
    return {
        "worker_profile": _worker_profile(str(user.id)),
        "skill_ids": _worker_skill_ids(str(user.id)),
    }


@router.patch("/worker")
def update_worker_profile(payload: WorkerProfileUpdate, user=Depends(get_current_user)):
    profile = _profile_or_404(str(user.id))
    _require_role(profile, "worker")
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    for key, value in patch.items():
        if value is None and key != "bio":
            raise HTTPException(status_code=422, detail=f"{key} cannot be null.")
    try:
        result = (
            admin_db.table("worker_profiles")
            .update(patch)
            .eq("user_id", str(user.id))
            .execute()
        )
    except Exception as e:
        print(f"Worker profile update failed: {e!r}")
        raise HTTPException(
            status_code=500,
            detail="Could not update worker profile."
        )
    if not result.data:
        raise HTTPException(status_code=400, detail="Worker profile update did not return a saved record.")
    return {"message": "Worker profile updated successfully.", "worker_profile": result.data[0]}


@router.put("/skills")
def replace_worker_skills(payload: SkillSelection, user=Depends(get_current_user)):
    """Replace selected worker skills; validates IDs against the skills table."""
    profile = _profile_or_404(str(user.id))
    _require_role(profile, "worker")

    valid_result = admin_db.table("skills").select("id").in_("id", payload.skill_ids).execute()
    valid_ids = {int(row["id"]) for row in (valid_result.data or [])}
    invalid_ids = sorted(set(payload.skill_ids) - valid_ids)
    if invalid_ids:
        raise HTTPException(status_code=422, detail={"invalid_skill_ids": invalid_ids})

    user_id = str(user.id)
    current_ids = set(_worker_skill_ids(user_id))
    requested_ids = set(payload.skill_ids)
    to_add = sorted(requested_ids - current_ids)
    to_remove = sorted(current_ids - requested_ids)

    try:
        if to_add:
            admin_db.table("worker_profile_skills").insert(
                [{"user_id": user_id, "skill_id": skill_id} for skill_id in to_add]
            ).execute()
        if to_remove:
            (
                admin_db.table("worker_profile_skills")
                .delete()
                .eq("user_id", user_id)
                .in_("skill_id", to_remove)
                .execute()
            )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not save skills. Reload the profile and try again.",
        ) from exc

    saved = _worker_skill_ids(user_id)
    return {"message": "Skills updated successfully.", "skill_ids": saved}


@router.get("/employer")
def get_employer_profile(user=Depends(get_current_user)):
    profile = _profile_or_404(str(user.id))
    _require_role(profile, "employer")
    return {"employer_profile": _employer_profile(str(user.id))}


@router.patch("/employer")
def update_employer_profile(payload: EmployerProfileUpdate, user=Depends(get_current_user)):
    """Update business details but never expose self-service verification changes."""
    profile = _profile_or_404(str(user.id))
    _require_role(profile, "employer")
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    for key, value in patch.items():
        if value is None and key == "organisation_name":
            raise HTTPException(status_code=422, detail="organisation_name cannot be null.")
    try:
        result = (
            admin_db.table("employer_profiles")
            .update(patch)
            .eq("user_id", str(user.id))
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not update employer profile.") from exc
    if not result.data:
        raise HTTPException(status_code=400, detail="Employer profile update did not return a saved record.")
    return {"message": "Employer profile updated successfully.", "employer_profile": result.data[0]}
