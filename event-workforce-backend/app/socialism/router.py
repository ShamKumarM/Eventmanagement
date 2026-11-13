"""Unified social connections: worker follows, employer follows, and worker-to-worker chat.

Workers may follow workers and employers. Employers are read-only from the follow perspective:
they cannot follow anyone and cannot use chat. Worker chat is enabled only when the
two workers follow each other (mutual follow).
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.applications.deps import get_current_worker, get_current_employer
from app.auth.db import admin_db
from app.auth.deps import get_current_user
from app.jobs.schemas import JobStatus, today_ist
from . import service
from .deps import get_current_member
from .schemas import ChatMessageCreate, WorkerFollowCreate

router = APIRouter(prefix="/socialism", tags=["Socialism"])


def _uid(ctx) -> str:
    return str(ctx["user"].id)


def _profile_card(user_id: str) -> dict:
    card = service.worker_cards([user_id]).get(user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Worker not found.")
    return card


def _is_following(follower_id: str, followed_id: str) -> bool:
    rows = (admin_db.table("worker_follows").select("follower_id")
            .eq("follower_id", follower_id).eq("followed_id", followed_id).limit(1).execute()).data or []
    return bool(rows)


def _mutual_follow(user_a: str, user_b: str) -> bool:
    return _is_following(user_a, user_b) and _is_following(user_b, user_a)


def _require_mutual_follow(user_id: str, other_id: str) -> None:
    if not _mutual_follow(user_id, other_id):
        raise HTTPException(status_code=403, detail="You can chat after you both follow each other.")


def _chat(user_id: str, other_id: str) -> dict:
    low, high = sorted((user_id, other_id))
    rows = (admin_db.table("worker_chats")
            .select("id, worker_low, worker_high, created_at, last_message_at")
            .eq("worker_low", low).eq("worker_high", high).limit(1).execute()).data or []
    if not rows:
        try:
            rows = admin_db.table("worker_chats").insert({"worker_low": low, "worker_high": high}).execute().data or []
        except APIError:
            rows = (admin_db.table("worker_chats")
                    .select("id, worker_low, worker_high, created_at, last_message_at")
                    .eq("worker_low", low).eq("worker_high", high).limit(1).execute()).data or []
    if not rows:
        raise HTTPException(status_code=503, detail="Could not open this chat.")
    return rows[0]


# ------------------------------- worker directory and follows
@router.get("/workers")
def find_workers(search: str | None = Query(None, max_length=80),
                 limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                 ctx=Depends(get_current_worker)):
    me = _uid(ctx)
    query = (admin_db.table("profiles").select("id, full_name, avatar_url", count="exact")
             .eq("role", "worker").eq("role_selected", True).neq("id", me))
    if search and search.strip():
        query = query.ilike("full_name", f"%{search.strip()}%")
    result = query.order("full_name").range(offset, offset + limit - 1).execute()
    items = result.data or []
    followed = {r["followed_id"] for r in (
        admin_db.table("worker_follows").select("followed_id")
        .eq("follower_id", me).in_("followed_id", [x["id"] for x in items]).execute()).data or []} if items else set()
    for item in items:
        item["is_following"] = item["id"] in followed
        item["can_chat"] = _mutual_follow(me, item["id"])
    return {"items": items, "total": result.count or 0, "limit": limit, "offset": offset}


@router.post("/workers/{worker_id}/follow", status_code=status.HTTP_201_CREATED)
def follow_worker(worker_id: UUID, ctx=Depends(get_current_worker)):
    me, other = _uid(ctx), str(worker_id)
    if me == other:
        raise HTTPException(status_code=422, detail="You cannot follow yourself.")
    _profile_card(other)
    try:
        admin_db.table("worker_follows").insert({"follower_id": me, "followed_id": other}).execute()
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            raise HTTPException(status_code=409, detail="You already follow this worker.") from exc
        raise HTTPException(status_code=503, detail="Could not follow this worker.") from exc
    return {"message": "You are now following this worker.", "worker_id": other,
            "is_following": True, "can_chat": _mutual_follow(me, other)}


@router.delete("/workers/{worker_id}/follow")
def unfollow_worker(worker_id: UUID, ctx=Depends(get_current_worker)):
    me, other = _uid(ctx), str(worker_id)
    removed = (admin_db.table("worker_follows").delete()
               .eq("follower_id", me).eq("followed_id", other).execute()).data or []
    if not removed:
        raise HTTPException(status_code=404, detail="You are not following this worker.")
    return {"message": "Worker unfollowed.", "worker_id": other,
            "is_following": False, "can_chat": False}


@router.get("/workers/me/following")
def my_worker_following(limit: int = Query(25, ge=1, le=100),
                        offset: int = Query(0, ge=0), ctx=Depends(get_current_worker)):
    me = _uid(ctx)
    result = (admin_db.table("worker_follows").select("followed_id, created_at", count="exact")
              .eq("follower_id", me).order("created_at", desc=True)
              .range(offset, offset + limit - 1).execute())
    rows = result.data or []
    cards = service.worker_cards([r["followed_id"] for r in rows])
    items = [{**cards[r["followed_id"]], "followed_at": r["created_at"],
              "can_chat": _mutual_follow(me, r["followed_id"])}
             for r in rows if r["followed_id"] in cards]
    return {"items": items, "total": result.count or 0, "limit": limit, "offset": offset}


@router.get("/workers/me/followers")
def my_worker_followers(limit: int = Query(25, ge=1, le=100),
                        offset: int = Query(0, ge=0), ctx=Depends(get_current_worker)):
    me = _uid(ctx)
    result = (admin_db.table("worker_follows").select("follower_id, created_at", count="exact")
              .eq("followed_id", me).order("created_at", desc=True)
              .range(offset, offset + limit - 1).execute())
    rows = result.data or []
    cards = service.worker_cards([r["follower_id"] for r in rows])
    items = [{**cards[r["follower_id"]], "followed_at": r["created_at"],
              "is_following_back": _is_following(me, r["follower_id"])}
             for r in rows if r["follower_id"] in cards]
    return {"items": items, "total": result.count or 0, "limit": limit, "offset": offset}


# -------------------------------- employer discovery and follow (workers only)
@router.get("/employers")
def search_employers(search: str | None = Query(None, max_length=80),
                     verified_only: bool = False,
                     limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                     member=Depends(get_current_member)):
    query = admin_db.table("employer_profiles").select("user_id", count="exact")
    if search and search.strip():
        query = query.ilike("organisation_name", f"%{search.strip()}%")
    if verified_only:
        query = query.eq("verification_status", "approved")
    result = query.order("organisation_name").range(offset, offset + limit - 1).execute()
    viewer = str(member["user"].id) if member["profile"].get("role") == "worker" else None
    return {"items": service.employer_cards([r["user_id"] for r in (result.data or [])], viewer),
            "total": result.count or 0, "limit": limit, "offset": offset}


@router.get("/employers/most-followed")
def most_followed_employers(limit: int = Query(10, ge=1, le=50),
                             verified_only: bool = False, member=Depends(get_current_member)):
    query = admin_db.table("employer_follower_counts").select("employer_id, follower_count")
    if verified_only:
        query = query.eq("verified", True)
    rows = query.order("follower_count", desc=True).order("employer_id").limit(limit).execute().data or []
    viewer = str(member["user"].id) if member["profile"].get("role") == "worker" else None
    return {"items": service.employer_cards([r["employer_id"] for r in rows], viewer), "limit": limit}


@router.get("/employers/{employer_id}")
def get_employer(employer_id: UUID, member=Depends(get_current_member)):
    viewer = str(member["user"].id) if member["profile"].get("role") == "worker" else None
    cards = service.employer_cards([str(employer_id)], viewer)
    if not cards:
        raise HTTPException(status_code=404, detail="Employer not found.")
    return {"employer": cards[0]}


@router.post("/employers/{employer_id}/follow", status_code=status.HTTP_201_CREATED)
def follow_employer(employer_id: UUID, ctx=Depends(get_current_worker)):
    me, eid = _uid(ctx), str(employer_id)
    card = service.employer_cards([eid], me)
    if not card:
        raise HTTPException(status_code=404, detail="Employer not found.")
    try:
        admin_db.table("employer_follows").insert({"worker_id": me, "employer_id": eid}).execute()
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            raise HTTPException(status_code=409, detail="You already follow this employer.") from exc
        raise HTTPException(status_code=503, detail="Could not follow this employer.") from exc
    count = (admin_db.table("employer_follower_counts").select("follower_count")
             .eq("employer_id", eid).limit(1).execute()).data or []
    return {"message": "You are now following this employer.", "employer_id": eid,
            "is_following": True, "follower_count": count[0]["follower_count"] if count else 1}


@router.delete("/employers/{employer_id}/follow")
def unfollow_employer(employer_id: UUID, ctx=Depends(get_current_worker)):
    me, eid = _uid(ctx), str(employer_id)
    removed = (admin_db.table("employer_follows").delete()
               .eq("worker_id", me).eq("employer_id", eid).execute()).data or []
    if not removed:
        raise HTTPException(status_code=404, detail="You are not following this employer.")
    count = (admin_db.table("employer_follower_counts").select("follower_count")
             .eq("employer_id", eid).limit(1).execute()).data or []
    return {"message": "You unfollowed this employer.", "employer_id": eid,
            "is_following": False, "follower_count": count[0]["follower_count"] if count else 0}


@router.get("/employers/me/following")
def my_employer_following(limit: int = Query(25, ge=1, le=100),
                          offset: int = Query(0, ge=0), ctx=Depends(get_current_worker)):
    me = _uid(ctx)
    result = (admin_db.table("employer_follows").select("employer_id, created_at", count="exact")
              .eq("worker_id", me).order("created_at", desc=True)
              .range(offset, offset + limit - 1).execute())
    cards = {c["id"]: c for c in service.employer_cards([r["employer_id"] for r in (result.data or [])], me)}
    items = [{**cards[r["employer_id"]], "followed_at": r["created_at"]}
             for r in (result.data or []) if r["employer_id"] in cards]
    return {"items": items, "total": result.count or 0, "limit": limit, "offset": offset}


@router.get("/employers/me/followers")
def my_employer_followers(limit: int = Query(25, ge=1, le=100),
                          offset: int = Query(0, ge=0), user=Depends(get_current_employer)):
    me = str(user.id)
    result = (admin_db.table("employer_follows").select("worker_id, created_at", count="exact")
              .eq("employer_id", me).order("created_at", desc=True)
              .range(offset, offset + limit - 1).execute())
    rows = result.data or []
    cards = service.worker_cards([r["worker_id"] for r in rows])
    return {"items": [{**cards[r["worker_id"]], "followed_at": r["created_at"]}
                      for r in rows if r["worker_id"] in cards],
            "total": result.count or 0, "limit": limit, "offset": offset}


# -------------------------------- worker-to-worker chat (mutual follow required)
@router.get("/chats")
def list_chats(limit: int = Query(25, ge=1, le=100),
               offset: int = Query(0, ge=0), ctx=Depends(get_current_worker)):
    me = _uid(ctx)
    outgoing = {r["followed_id"] for r in (
        admin_db.table("worker_follows").select("followed_id").eq("follower_id", me).execute()).data or []}
    incoming = {r["follower_id"] for r in (
        admin_db.table("worker_follows").select("follower_id").eq("followed_id", me).execute()).data or []}
    mutual = outgoing & incoming
    if not mutual:
        return {"items": [], "limit": limit, "offset": offset}
    result = (admin_db.table("worker_chats")
              .select("id, worker_low, worker_high, created_at, last_message_at")
              .or_(f"worker_low.eq.{me},worker_high.eq.{me}")
              .order("last_message_at", desc=True, nullsfirst=False)
              .range(offset, offset + limit - 1).execute())
    chats = [c for c in (result.data or [])
             if (c["worker_high"] if c["worker_low"] == me else c["worker_low"]) in mutual]
    ids = [c["worker_high"] if c["worker_low"] == me else c["worker_low"] for c in chats]
    cards = service.worker_cards(ids)
    for chat, other in zip(chats, ids):
        chat["worker"] = cards.get(other)
        latest = (admin_db.table("worker_chat_messages")
                  .select("id, sender_id, message_type, body, shared_job_snapshot, created_at")
                  .eq("chat_id", chat["id"]).order("created_at", desc=True).limit(1).execute()).data or []
        chat["last_message"] = latest[0] if latest else None
    return {"items": chats, "limit": limit, "offset": offset}


@router.get("/chats/{worker_id}/messages")
def list_chat_messages(worker_id: UUID, limit: int = Query(50, ge=1, le=100),
                       before: datetime | None = Query(None), ctx=Depends(get_current_worker)):
    me, other = _uid(ctx), str(worker_id)
    _require_mutual_follow(me, other)
    chat = _chat(me, other)
    query = (admin_db.table("worker_chat_messages")
             .select("id, chat_id, sender_id, message_type, body, shared_job_id, shared_job_snapshot, created_at")
             .eq("chat_id", chat["id"]))
    if before:
        query = query.lt("created_at", before.isoformat())
    result = query.order("created_at", desc=True).limit(limit).execute()
    return {"chat_id": chat["id"], "worker": _profile_card(other),
            "items": list(reversed(result.data or [])), "limit": limit}


@router.post("/chats/{worker_id}/messages", status_code=status.HTTP_201_CREATED)
def send_chat_message(worker_id: UUID, payload: ChatMessageCreate, ctx=Depends(get_current_worker)):
    me, other = _uid(ctx), str(worker_id)
    if me == other:
        raise HTTPException(status_code=422, detail="You cannot message yourself.")
    _require_mutual_follow(me, other)
    chat = _chat(me, other)
    row = {"chat_id": chat["id"], "sender_id": me}
    if payload.body is not None:
        row.update(message_type="text", body=payload.body)
    else:
        jobs = (admin_db.table("jobs")
                .select("id, title, category_id, job_date, start_time, end_time, area, district, city, state, venue_name, salary_per_worker, payment_type, status, job_categories(name)")
                .eq("id", str(payload.job_id)).limit(1).execute()).data or []
        if not jobs or jobs[0].get("status") != JobStatus.open.value or jobs[0].get("job_date", "") < today_ist().isoformat():
            raise HTTPException(status_code=404, detail="Only active job postings can be shared in chat.")
        row.update(message_type="job_share", shared_job_id=jobs[0]["id"], shared_job_snapshot=jobs[0])
    try:
        result = admin_db.table("worker_chat_messages").insert(row).execute()
    except APIError as exc:
        raise HTTPException(status_code=503, detail="Could not send the chat message.") from exc
    return result.data[0]
