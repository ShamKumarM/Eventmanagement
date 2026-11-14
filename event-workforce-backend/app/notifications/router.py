"""Worker and employer in-app notification inbox."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.db import admin_db
from app.auth.deps import get_current_user
from app.applications.deps import get_current_worker, get_current_employer

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _list_for_user(user_id: str, limit: int, offset: int):
    result = (admin_db.table("notifications")
              .select("id, type, title, body, data, is_read, read_at, created_at", count="exact")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .range(offset, offset + limit - 1).execute())
    unread = (admin_db.table("notifications").select("id", count="exact")
              .eq("user_id", user_id).eq("is_read", False).execute().count or 0)
    return {"items": result.data or [], "total": result.count or 0,
            "unread_count": unread, "limit": limit, "offset": offset}


@router.get("")
def list_notifications(limit: int = Query(30, ge=1, le=100),
                       offset: int = Query(0, ge=0),
                       user=Depends(get_current_user)):
    return _list_for_user(str(user.id), limit, offset)


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: UUID, user=Depends(get_current_user)):
    result = (admin_db.table("notifications")
              .update({"is_read": True})
              .eq("id", str(notification_id)).eq("user_id", str(user.id))
              .select("id, is_read, read_at").execute())
    if not result.data:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"message": "Notification marked as read.", "notification": result.data[0]}


@router.post("/read-all")
def mark_all_notifications_read(user=Depends(get_current_user)):
    result = (admin_db.table("notifications")
              .update({"is_read": True})
              .eq("user_id", str(user.id)).eq("is_read", False)
              .select("id").execute())
    return {"message": "All notifications marked as read.", "updated": len(result.data or [])}
