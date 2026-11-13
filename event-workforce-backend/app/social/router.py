"""Worker friend requests, friend lists, direct chats, and job sharing."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.applications.deps import get_current_worker
from app.auth.db import admin_db
from app.jobs.schemas import JobStatus, today_ist

from .schemas import FriendRequestAction, FriendRequestCreate, FriendRequestRespond, ChatMessageCreate

router = APIRouter(prefix="/social", tags=["Worker Social"])


def _uid(ctx) -> str:
    return str(ctx["user"].id)


def _worker_card(user_id: str) -> dict:
    rows = (
        admin_db.table("profiles")
        .select("id, full_name, avatar_url")
        .eq("id", user_id)
        .eq("role", "worker")
        .eq("role_selected", True)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Worker not found.")
    row = rows[0]
    return {"id": row["id"], "full_name": row.get("full_name"), "avatar_url": row.get("avatar_url")}


def _friendship(user_id: str, other_id: str) -> dict | None:
    low, high = sorted((user_id, other_id))
    rows = (
        admin_db.table("worker_friendships")
        .select("worker_low, worker_high, created_at")
        .eq("worker_low", low)
        .eq("worker_high", high)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def _require_friend(user_id: str, other_id: str) -> None:
    if not _friendship(user_id, other_id):
        raise HTTPException(status_code=403, detail="You can chat only with an accepted worker connection.")


def _chat(user_id: str, other_id: str) -> dict:
    low, high = sorted((user_id, other_id))
    rows = (
        admin_db.table("worker_chats")
        .select("id, worker_low, worker_high, created_at, last_message_at")
        .eq("worker_low", low)
        .eq("worker_high", high)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        # Normally created atomically when a request is accepted. This also
        # repairs a missing chat row after a manual database restore.
        try:
            created = admin_db.table("worker_chats").insert({"worker_low": low, "worker_high": high}).execute()
            rows = created.data or []
        except APIError:
            rows = (
                admin_db.table("worker_chats")
                .select("id, worker_low, worker_high, created_at, last_message_at")
                .eq("worker_low", low)
                .eq("worker_high", high)
                .limit(1)
                .execute()
            ).data or []
    if not rows:
        raise HTTPException(status_code=503, detail="Could not open this chat.")
    return rows[0]


@router.post("/friend-requests", status_code=status.HTTP_201_CREATED)
def send_friend_request(payload: FriendRequestCreate, ctx=Depends(get_current_worker)):
    sender_id = _uid(ctx)
    recipient_id = str(payload.recipient_id)
    if sender_id == recipient_id:
        raise HTTPException(status_code=422, detail="You cannot send a friend request to yourself.")
    _worker_card(recipient_id)
    if _friendship(sender_id, recipient_id):
        raise HTTPException(status_code=409, detail="You are already connected with this worker.")

    pending = (
        admin_db.table("worker_friend_requests")
        .select("id, sender_id, recipient_id, status, created_at")
        .eq("status", "pending")
        .or_(f"and(sender_id.eq.{sender_id},recipient_id.eq.{recipient_id}),and(sender_id.eq.{recipient_id},recipient_id.eq.{sender_id})")
        .limit(1)
        .execute()
    ).data or []
    if pending:
        req = pending[0]
        if req["recipient_id"] == sender_id:
            raise HTTPException(status_code=409, detail={"message": "This worker already requested to connect with you.", "request_id": req["id"], "action": "accept_or_reject"})
        raise HTTPException(status_code=409, detail="A friend request is already pending.")

    try:
        result = admin_db.table("worker_friend_requests").insert({
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "status": "pending",
        }).execute()
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            raise HTTPException(status_code=409, detail="A friend request is already pending.") from exc
        raise HTTPException(status_code=503, detail="Could not send the friend request.") from exc
    return {"message": "Friend request sent.", "request": result.data[0]}


@router.get("/workers")
def find_workers(
    search: str | None = Query(default=None, max_length=80),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx=Depends(get_current_worker),
):
    """Search the worker directory without returning private contact details."""
    user_id = _uid(ctx)
    query = (
        admin_db.table("profiles")
        .select("id, full_name, avatar_url", count="exact")
        .eq("role", "worker")
        .eq("role_selected", True)
        .neq("id", user_id)
    )
    search_text = (search or "").strip()
    if search_text:
        query = query.ilike("full_name", f"%{search_text}%")
    result = query.order("full_name").range(offset, offset + limit - 1).execute()
    return {"items": result.data or [], "total": result.count or 0, "limit": limit, "offset": offset}


@router.get("/friend-requests")
def list_friend_requests(
    folder: str = Query("incoming", pattern="^(incoming|outgoing)$"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx=Depends(get_current_worker),
):
    user_id = _uid(ctx)
    column = "recipient_id" if folder == "incoming" else "sender_id"
    other_column = "sender_id" if folder == "incoming" else "recipient_id"
    result = (
        admin_db.table("worker_friend_requests")
        .select("id, sender_id, recipient_id, status, created_at", count="exact")
        .eq(column, user_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    requests = result.data or []
    if requests:
        profiles = (
            admin_db.table("profiles")
            .select("id, full_name, avatar_url")
            .in_("id", list({row[other_column] for row in requests}))
            .execute()
        ).data or []
        cards = {row["id"]: {"id": row["id"], "full_name": row.get("full_name"), "avatar_url": row.get("avatar_url")} for row in profiles}
        for row in requests:
            row["worker"] = cards.get(row[other_column])
    return {"items": requests, "total": result.count or 0, "limit": limit, "offset": offset}


@router.post("/friend-requests/{request_id}/respond")
def respond_to_friend_request(request_id: UUID, payload: FriendRequestRespond, ctx=Depends(get_current_worker)):
    try:
        result = admin_db.rpc("respond_to_worker_friend_request", {
            "p_request_id": str(request_id),
            "p_actor_id": _uid(ctx),
            "p_action": payload.action.value,
        }).execute()
    except APIError as exc:
        message = str(exc).lower()
        if "request_not_found" in message:
            raise HTTPException(status_code=404, detail="Friend request not found.") from exc
        if "request_not_pending" in message:
            raise HTTPException(status_code=409, detail="This friend request has already been handled.") from exc
        if "not_allowed" in message:
            raise HTTPException(status_code=403, detail="You cannot perform this action on that request.") from exc
        raise HTTPException(status_code=503, detail="Could not update the friend request.") from exc
    messages = {
        FriendRequestAction.accept: "Friend request accepted.",
        FriendRequestAction.reject: "Friend request rejected.",
        FriendRequestAction.cancel: "Friend request cancelled.",
    }
    return {"message": messages[payload.action], "request": result.data}


@router.get("/friends")
def list_friends(ctx=Depends(get_current_worker)):
    user_id = _uid(ctx)
    result = (
        admin_db.table("worker_friendships")
        .select("worker_low, worker_high, created_at")
        .or_(f"worker_low.eq.{user_id},worker_high.eq.{user_id}")
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data or []
    other_ids = [row["worker_high"] if row["worker_low"] == user_id else row["worker_low"] for row in rows]
    if not other_ids:
        return []
    profiles = (
        admin_db.table("profiles")
        .select("id, full_name, avatar_url")
        .in_("id", other_ids)
        .execute()
    ).data or []
    cards = {row["id"]: {"id": row["id"], "full_name": row.get("full_name"), "avatar_url": row.get("avatar_url")} for row in profiles}
    return [{**cards.get(other_id, {"id": other_id}), "connected_at": row["created_at"]} for row, other_id in zip(rows, other_ids)]


@router.delete("/friends/{worker_id}")
def remove_friend(worker_id: UUID, ctx=Depends(get_current_worker)):
    user_id, other_id = _uid(ctx), str(worker_id)
    if user_id == other_id:
        raise HTTPException(status_code=422, detail="That is not a valid connection.")
    low, high = sorted((user_id, other_id))
    result = (
        admin_db.table("worker_friendships")
        .delete()
        .eq("worker_low", low)
        .eq("worker_high", high)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Worker connection not found.")
    return {"message": "Worker connection removed."}


@router.get("/chats")
def list_chats(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx=Depends(get_current_worker),
):
    user_id = _uid(ctx)
    friendship_rows = (
        admin_db.table("worker_friendships")
        .select("worker_low, worker_high")
        .or_(f"worker_low.eq.{user_id},worker_high.eq.{user_id}")
        .execute()
    ).data or []
    friend_ids = {
        row["worker_high"] if row["worker_low"] == user_id else row["worker_low"]
        for row in friendship_rows
    }
    if not friend_ids:
        return {"items": [], "limit": limit, "offset": offset}
    result = (
        admin_db.table("worker_chats")
        .select("id, worker_low, worker_high, created_at, last_message_at")
        .or_(f"worker_low.eq.{user_id},worker_high.eq.{user_id}")
        .order("last_message_at", desc=True, nullsfirst=False)
        .range(offset, offset + limit - 1)
        .execute()
    )
    chats = [
        chat for chat in (result.data or [])
        if (chat["worker_high"] if chat["worker_low"] == user_id else chat["worker_low"]) in friend_ids
    ]
    other_ids = [chat["worker_high"] if chat["worker_low"] == user_id else chat["worker_low"] for chat in chats]
    profiles = []
    if other_ids:
        profiles = (
            admin_db.table("profiles")
            .select("id, full_name, avatar_url")
            .in_("id", other_ids)
            .execute()
        ).data or []
    cards = {row["id"]: {"id": row["id"], "full_name": row.get("full_name"), "avatar_url": row.get("avatar_url")} for row in profiles}
    for chat, other_id in zip(chats, other_ids):
        chat["worker"] = cards.get(other_id)
        latest = (
            admin_db.table("worker_chat_messages")
            .select("id, sender_id, message_type, body, shared_job_snapshot, created_at")
            .eq("chat_id", chat["id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        chat["last_message"] = latest[0] if latest else None
    return {"items": chats, "limit": limit, "offset": offset}


@router.get("/chats/{worker_id}/messages")
def list_chat_messages(
    worker_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before: datetime | None = Query(default=None, description="ISO timestamp cursor; returns older messages."),
    ctx=Depends(get_current_worker),
):
    user_id, other_id = _uid(ctx), str(worker_id)
    _require_friend(user_id, other_id)
    chat = _chat(user_id, other_id)
    query = (
        admin_db.table("worker_chat_messages")
        .select("id, chat_id, sender_id, message_type, body, shared_job_id, shared_job_snapshot, created_at")
        .eq("chat_id", chat["id"])
    )
    if before:
        query = query.lt("created_at", before.isoformat())
    result = query.order("created_at", desc=True).limit(limit).execute()
    messages = list(reversed(result.data or []))
    return {"chat_id": chat["id"], "worker": _worker_card(other_id), "items": messages, "limit": limit}


@router.post("/chats/{worker_id}/messages", status_code=status.HTTP_201_CREATED)
def send_chat_message(worker_id: UUID, payload: ChatMessageCreate, ctx=Depends(get_current_worker)):
    user_id, other_id = _uid(ctx), str(worker_id)
    if user_id == other_id:
        raise HTTPException(status_code=422, detail="You cannot message yourself.")
    _require_friend(user_id, other_id)
    chat = _chat(user_id, other_id)

    row = {"chat_id": chat["id"], "sender_id": user_id}
    if payload.body is not None:
        row.update(message_type="text", body=payload.body)
    else:
        job_rows = (
            admin_db.table("jobs")
            .select("id, title, category_id, job_date, start_time, end_time, area, district, city, state, venue_name, salary_per_worker, payment_type, status, job_categories(name)")
            .eq("id", str(payload.job_id))
            .limit(1)
            .execute()
        ).data or []
        if not job_rows or job_rows[0].get("status") != JobStatus.open.value or job_rows[0].get("job_date", "") < today_ist().isoformat():
            raise HTTPException(status_code=404, detail="Only active job postings can be shared in chat.")
        job = job_rows[0]
        row.update(message_type="job_share", shared_job_id=job["id"], shared_job_snapshot=job)

    try:
        result = admin_db.table("worker_chat_messages").insert(row).execute()
    except APIError as exc:
        raise HTTPException(status_code=503, detail="Could not send the chat message.") from exc
    return result.data[0]
