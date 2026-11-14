"""Best-effort in-app notification writer."""
import logging
from typing import Any

from app.auth.db import admin_db

logger = logging.getLogger(__name__)


def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Persist an in-app notification; notification failures never undo core actions."""
    try:
        admin_db.table("notifications").insert({
            "user_id": str(user_id),
            "type": notification_type,
            "title": title,
            "body": body,
            "data": data or {},
        }).execute()
    except Exception:
        logger.exception("Could not create notification type=%s user=%s", notification_type, user_id)
