"""Role and eligibility dependencies for the Applications module.

Uses the shared auth dependency (app.auth.deps.get_current_user) and the
trusted service-role client (app.auth.db.admin_db), like the Profile module.
"""
from fastapi import Depends, HTTPException, status

from app.auth.db import admin_db
from app.auth.deps import get_current_user


def _profile(user_id: str) -> dict:
    res = (
        admin_db.table("profiles")
        .select("id, full_name, phone, role, role_selected")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile not found.")
    return res.data[0]


def _require(profile: dict, role: str) -> None:
    if profile.get("role") != role or not profile.get("role_selected"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Only users who selected the {role} role can use this endpoint.",
        )


def get_current_worker(user=Depends(get_current_user)):
    """Rules 3 and 4: only a worker passes; employers get 403."""
    profile = _profile(str(user.id))
    _require(profile, "worker")
    return {"user": user, "profile": profile}


def get_current_employer(user=Depends(get_current_user)):
    _require(_profile(str(user.id)), "employer")
    return user


# Same rule as app/profile/router.py (GET /profile/completion):
# five required fields, 20% each, eligible only at 100%.
# TODO(coordinate with Profile developer): ideally they expose one shared
# function and both modules import it, so the rule lives in one place.
def assert_worker_eligible(user_id: str, profile: dict) -> None:
    worker = (
        admin_db.table("worker_profiles")
        .select("preferred_area, experience_level")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data
    worker = worker[0] if worker else {}
    skills = (
        admin_db.table("worker_profile_skills")
        .select("skill_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data

    done = {
        "full_name": bool((profile.get("full_name") or "").strip()),
        "phone": bool((profile.get("phone") or "").strip()),
        "preferred_area": bool((worker.get("preferred_area") or "").strip()),
        "skills": len(skills or []) > 0,
        "experience_level": bool((worker.get("experience_level") or "").strip()),
    }
    missing = [k for k, ok in done.items() if not ok]
    if missing:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "message": "Complete your profile before applying for jobs.",
                "completion_percentage": 100 - 20 * len(missing),
                "missing_fields": missing,
            },
        )