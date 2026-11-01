
"""Authentication dependencies used by the jobs module."""
from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from .db import db


def get_current_employer(user=Depends(get_current_user)):
    """Allow job-management routes only for users who selected employer."""
    result = (
        db.table("profiles")
        .select("role, role_selected")
        .eq("id", str(user.id))
        .maybe_single()
        .execute()
    )

    profile = result.data

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Profile not found.",
        )

    if profile.get("role") != "employer" or not profile.get("role_selected"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users who selected the employer role can manage jobs.",
        )

    return user
