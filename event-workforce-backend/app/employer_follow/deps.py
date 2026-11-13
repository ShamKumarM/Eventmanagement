"""Authorization dependencies for the employer follow module.

Worker and employer checks are reused from app.applications.deps so the role rule lives in one place.
"""
from fastapi import Depends, HTTPException, status

from app.applications.deps import get_current_employer, get_current_worker  # noqa: F401 (re-exported)
from app.auth.db import admin_db
from app.auth.deps import get_current_user

MEMBER_ROLES = {"worker", "employer", "admin"}


def get_current_member(user=Depends(get_current_user)):
    """Any signed-in user who finished role selection (used for read-only public employer data)."""
    rows = (
        admin_db.table("profiles")
        .select("id, role, role_selected")
        .eq("id", str(user.id))
        .limit(1)
        .execute()
    ).data or []
    if not rows or rows[0].get("role") not in MEMBER_ROLES or not rows[0].get("role_selected"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Finish selecting your role to use this feature.")
    return {"user": user, "profile": rows[0]}