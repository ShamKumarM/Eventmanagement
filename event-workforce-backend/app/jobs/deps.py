"""Auth dependencies for the jobs module.

TEMPORARY: get_current_user mirrors main.py. Once the teammate moves his
version into a shared module (e.g. auth_deps.py), import it from there.
"""
from fastapi import Depends, Header, HTTPException

from .db import db


def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        response = db.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid access token")
        return response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


def get_current_employer(user=Depends(get_current_user)):
    # TODO: once the teammate adds a profiles table with a role column,
    # check that role == "employer" (and that the employer is verified).
    #   row = db.table("profiles").select("role, is_verified") \
    #           .eq("id", str(user.id)).single().execute().data
    #   if row["role"] != "employer": raise HTTPException(403, "Employers only")
    return user
