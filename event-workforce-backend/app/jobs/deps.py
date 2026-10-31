"""Auth dependencies for the jobs module."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        response = db.auth.get_user(creds.credentials)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid access token")
        return response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


def get_current_employer(user=Depends(get_current_user)):
    res = (
        db.table("profiles")
        .select("role")
        .eq("id", str(user.id))
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=403, detail="Profile not found")
    if res.data[0]["role"] != "employer":
        raise HTTPException(status_code=403, detail="Only employers can do this")
    return user