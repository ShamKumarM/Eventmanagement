from fastapi import Depends, HTTPException, status
from app.auth.db import admin_db
from app.auth.deps import get_current_user

MEMBER_ROLES = {"worker", "employer", "admin"}


def get_current_member(user=Depends(get_current_user)):
    rows = (admin_db.table("profiles").select("id, role, role_selected")
            .eq("id", str(user.id)).limit(1).execute()).data or []
    if not rows or rows[0].get("role") not in MEMBER_ROLES or not rows[0].get("role_selected"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Finish selecting your role to use this feature.")
    return {"user": user, "profile": rows[0]}
