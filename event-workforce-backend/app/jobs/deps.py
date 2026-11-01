"""Authentication dependencies used by the jobs module."""
from fastapi import Depends

from app.auth.deps import get_current_user


def get_current_employer(user=Depends(get_current_user)):
    # TODO: enforce profiles.role == "employer" and any verification rules.
    # This structural refactor intentionally keeps the existing authorization
    # behavior unchanged; implement role enforcement as a separate change.
    return user
