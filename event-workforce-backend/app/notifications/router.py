"""Notifications API. Every route is scoped to the signed-in user's own notifications."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.db import admin_db

from .deps import get_current_member
from .service import attach_contacts

router = APIRouter(prefix="/notifications", tags=["Notifications"])

_COLUMNS = "id, type, title, body, data, read_at, created_at"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unread_count(user_id: str) -> int:
    return (
        admin_db.table("notifications").select("id", count="exact").eq("user_id", user_id).is_("read_at", "null").limit(1).execute()
    ).count or 0


@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_member),
):
    """Newest first. `application_selected` items carry the employer's contact details while the worker is still selected."""
    me = str(user.id)
    query = admin_db.table("notifications").select(_COLUMNS, count="exact").eq("user_id", me)
    if unread_only:
        query = query.is_("read_at", "null")
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    items = attach_contacts(result.data or [], me)
    return {"items": items, "total": result.count or 0, "limit": limit, "offset": offset, "unread_count": _unread_count(me)}


@router.get("/unread-count")
def unread_count(user=Depends(get_current_member)):
    return {"unread_count": _unread_count(str(user.id))}


@router.post("/read-all")
def mark_all_read(user=Depends(get_current_member)):
    updated = (
        admin_db.table("notifications").update({"read_at": _now()})
        .eq("user_id", str(user.id)).is_("read_at", "null").execute()
    ).data or []
    return {"message": "All notifications marked as read.", "updated": len(updated), "unread_count": 0}


@router.post("/{notification_id}/read")
def mark_read(notification_id: UUID, user=Depends(get_current_member)):
    """Idempotent. Someone else's notification looks exactly like a missing one (404)."""
    me, nid = str(user.id), str(notification_id)
    updated = (
        admin_db.table("notifications").update({"read_at": _now()})
        .eq("id", nid).eq("user_id", me).is_("read_at", "null").execute()
    ).data
    row = updated[0] if updated else None
    if row is None:
        existing = admin_db.table("notifications").select(_COLUMNS).eq("id", nid).eq("user_id", me).limit(1).execute().data
        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
        row = existing[0]
    return {"message": "Notification marked as read.", "notification": row, "unread_count": _unread_count(me)}