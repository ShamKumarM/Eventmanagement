"""Shared authentication dependencies for protected API routes."""
import logging

from fastapi import Header, HTTPException, status

from app.services.supabase_client import create_supabase_client

logger = logging.getLogger(__name__)


def _log_auth_error(action: str, exc: Exception) -> None:
    """Log diagnostics locally without returning provider details to clients."""
    logger.exception("%s failed (%s)", action, type(exc).__name__)
    for attribute in ("message", "status", "code", "details", "hint"):
        value = getattr(exc, attribute, None)
        if value:
            logger.error("Supabase %s: %s", attribute, value)


def get_current_user(authorization: str | None = Header(default=None)):
    """Validate a bearer access token with Supabase and return its user."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide an Authorization: Bearer <access_token> header.",
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token.")

    try:
        response = create_supabase_client().auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired session.")
        return response.user
    except HTTPException:
        raise
    except Exception as exc:
        _log_auth_error("Token verification", exc)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
        ) from exc
