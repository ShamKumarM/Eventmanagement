"""Employer follow system.

Workers follow employers; the verified badge and "most followed" ranking are separate things;
an employer's private contact details are released only after the employer accepts a request.

Route order matters: fixed paths (/employers/me/..., /employers/most-followed) are declared
BEFORE /employers/{employer_id}, otherwise "me" would be read as an employer id.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.auth.db import admin_db

from .deps import get_current_employer, get_current_member, get_current_worker
from .schemas import ContactRequestCreate, ContactRequestRespond, ContactRequestStatus
from . import service

router = APIRouter(
    prefix="/employer-follow",
    tags=["Employer Follow"]
)


def _viewer_worker_id(member: dict) -> str | None:
    return str(member["user"].id) if member["profile"].get("role") == "worker" else None


def _page(rows_total, items, limit, offset, **extra):
    return {"items": items, "total": rows_total or 0, "limit": limit, "offset": offset, **extra}


# =============================================================== discover employers (public data only)
@router.get("/employers")
def search_employers(
    search: str | None = Query(default=None, max_length=80),
    verified_only: bool = Query(default=False),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    member=Depends(get_current_member),
):
    """Search/browse employers by organisation name. Never returns private contact details."""
    query = admin_db.table("employer_profiles").select("user_id", count="exact")
    if search and search.strip():
        query = query.ilike("organisation_name", service.like_pattern(search))
    if verified_only:
        query = query.eq("verification_status", "approved")
    result = query.order("organisation_name").range(offset, offset + limit - 1).execute()
    ids = [row["user_id"] for row in (result.data or [])]
    return _page(result.count, service.build_cards(ids, _viewer_worker_id(member)), limit, offset)


@router.get("/employers/most-followed")
def most_followed_employers(
    limit: int = Query(10, ge=1, le=50),
    verified_only: bool = Query(default=False),
    member=Depends(get_current_member),
):
    """Ranking by number of unique followers. `verified` is shown separately and never affects rank."""
    query = admin_db.table("employer_follower_counts").select("employer_id, follower_count")
    if verified_only:
        query = query.eq("verified", True)
    rows = query.order("follower_count", desc=True).order("employer_id").limit(limit).execute().data or []
    cards = service.build_cards([r["employer_id"] for r in rows], _viewer_worker_id(member))
    for position, card in enumerate(cards, start=1):
        card["rank"] = position
    return {"items": cards, "limit": limit}


@router.get("/employers/me/following")
def my_following(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx=Depends(get_current_worker),
):
    """Employers the signed-in worker follows, newest first."""
    me = str(ctx["user"].id)
    result = (
        admin_db.table("employer_follows")
        .select("employer_id, created_at", count="exact")
        .eq("worker_id", me)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = result.data or []
    cards = {c["id"]: c for c in service.build_cards([r["employer_id"] for r in rows], me)}
    items = [{**cards[r["employer_id"]], "followed_at": r["created_at"]} for r in rows if r["employer_id"] in cards]
    return _page(result.count, items, limit, offset)


@router.get("/employers/me/followers")
def my_followers(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_employer),
):
    """Workers following the signed-in employer. Name and photo only: no phone or email."""
    me = str(user.id)
    result = (
        admin_db.table("employer_follows")
        .select("worker_id, created_at", count="exact")
        .eq("employer_id", me)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = result.data or []
    workers = service.worker_cards([r["worker_id"] for r in rows])
    items = [
        {**workers[r["worker_id"]], "followed_at": r["created_at"]} for r in rows if r["worker_id"] in workers
    ]
    return _page(result.count, items, limit, offset, follower_count=result.count or 0)


@router.get("/employers/{employer_id}")
def get_employer(employer_id: UUID, member=Depends(get_current_member)):
    """Public employer profile. Private contact details are NOT included; see GET .../contact."""
    cards = service.build_cards([str(employer_id)], _viewer_worker_id(member))
    if not cards:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer not found.")
    return {"employer": cards[0]}


# =============================================================== follow / unfollow
@router.post("/employers/{employer_id}/follow", status_code=status.HTTP_201_CREATED)
def follow_employer(employer_id: UUID, ctx=Depends(get_current_worker)):
    me, eid = str(ctx["user"].id), str(employer_id)
    service.require_employer(eid)
    try:
        admin_db.table("employer_follows").insert({"worker_id": me, "employer_id": eid}).execute()
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            raise HTTPException(status.HTTP_409_CONFLICT, "You already follow this employer.") from exc
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not follow this employer.") from exc
    return {
        "message": "You are now following this employer.",
        "employer_id": eid,
        "is_following": True,
        "follower_count": service.follower_count(eid),
    }


@router.delete("/employers/{employer_id}/follow")
def unfollow_employer(employer_id: UUID, ctx=Depends(get_current_worker)):
    me, eid = str(ctx["user"].id), str(employer_id)
    removed = (
        admin_db.table("employer_follows").delete().eq("worker_id", me).eq("employer_id", eid).execute()
    ).data
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not following this employer.")
    # A still-pending contact request makes no sense once you stop following: cancel it.
    # An ACCEPTED request is left alone: only the employer can withdraw contact access (action "revoke").
    (
        admin_db.table("employer_contact_requests")
        .update({"status": "cancelled", "responded_at": service.now_iso()})
        .eq("worker_id", me).eq("employer_id", eid).eq("status", "pending")
        .execute()
    )
    return {
        "message": "You unfollowed this employer.",
        "employer_id": eid,
        "is_following": False,
        "follower_count": service.follower_count(eid),
    }


# =============================================================== contact access: worker side
@router.post("/employers/{employer_id}/contact-requests", status_code=status.HTTP_201_CREATED)
def request_contact_access(
    employer_id: UUID,
    payload: ContactRequestCreate | None = None,
    ctx=Depends(get_current_worker),
):
    """Ask an employer to share their contact details. Following alone never grants access."""
    me, eid = str(ctx["user"].id), str(employer_id)
    service.require_employer(eid)
    if eid not in service.following_set(me, [eid]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Follow this employer before requesting contact access.")

    current = service.contact_status(me, eid)
    if current == "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "This employer has already shared their contact details with you.")
    if current == "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a pending contact request for this employer.")

    try:
        created = (
            admin_db.table("employer_contact_requests")
            .insert({"worker_id": me, "employer_id": eid, "message": payload.message if payload else None})
            .execute()
        )
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":      # lost a race with a parallel request
            raise HTTPException(status.HTTP_409_CONFLICT, "You already have an active contact request for this employer.") from exc
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not send the contact request.") from exc
    return {"message": "Contact request sent. The employer must accept it before you can see their details.", "request": created.data[0]}


@router.get("/employers/{employer_id}/contact")
def get_employer_contact(employer_id: UUID, ctx=Depends(get_current_worker)):
    """The ONLY endpoint that returns private contact details, and only after the employer accepted."""
    me, eid = str(ctx["user"].id), str(employer_id)
    service.require_employer(eid)
    grant = (
        admin_db.table("employer_contact_requests")
        .select("id, responded_at")
        .eq("worker_id", me).eq("employer_id", eid).eq("status", "accepted")
        .limit(1).execute()
    ).data or []
    if not grant:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "message": "This employer has not shared their contact details with you.",
                "contact_access": {"status": service.contact_status(me, eid)},
            },
        )
    return {"employer_id": eid, "contact": service.release_contact(eid), "granted_at": grant[0]["responded_at"]}


@router.get("/contact-requests/mine")
def my_contact_requests(
    status_filter: ContactRequestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx=Depends(get_current_worker),
):
    """Status of the contact requests the signed-in worker has sent."""
    query = (
        admin_db.table("employer_contact_requests")
        .select("id, employer_id, status, message, created_at, responded_at", count="exact")
        .eq("worker_id", str(ctx["user"].id))
    )
    if status_filter:
        query = query.eq("status", status_filter.value)
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    rows = result.data or []
    employers = service.mini_employer_cards([r["employer_id"] for r in rows])
    for row in rows:
        row["employer"] = employers.get(row["employer_id"])
        row["contact_available"] = row["status"] == "accepted"
    return _page(result.count, rows, limit, offset)


def _diagnose_failed_update(request_id: UUID, actor_column: str, actor_id: str) -> HTTPException:
    """The guarded UPDATE changed nothing: say why (missing / someone else's / wrong state)."""
    rows = (
        admin_db.table("employer_contact_requests")
        .select("id, worker_id, employer_id, status").eq("id", str(request_id)).limit(1).execute()
    ).data or []
    if not rows:
        return HTTPException(status.HTTP_404_NOT_FOUND, "Contact request not found.")
    if rows[0][actor_column] != actor_id:
        return HTTPException(status.HTTP_403_FORBIDDEN, "You cannot act on this contact request.")
    return HTTPException(status.HTTP_409_CONFLICT, f"This request is already {rows[0]['status']}.")


@router.post("/contact-requests/{request_id}/cancel")
def cancel_contact_request(request_id: UUID, ctx=Depends(get_current_worker)):
    me = str(ctx["user"].id)
    updated = (
        admin_db.table("employer_contact_requests")
        .update({"status": "cancelled", "responded_at": service.now_iso()})
        .eq("id", str(request_id)).eq("worker_id", me).eq("status", "pending")
        .execute()
    ).data
    if not updated:
        raise _diagnose_failed_update(request_id, "worker_id", me)
    return {"message": "Contact request cancelled.", "request": updated[0]}


# =============================================================== contact access: employer side
@router.get("/contact-requests/incoming")
def incoming_contact_requests(
    status_filter: ContactRequestStatus | None = Query(default=ContactRequestStatus.pending, alias="status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_employer),
):
    """Contact requests addressed to the signed-in employer (pending by default)."""
    query = (
        admin_db.table("employer_contact_requests")
        .select("id, worker_id, status, message, created_at, responded_at", count="exact")
        .eq("employer_id", str(user.id))
    )
    if status_filter:
        query = query.eq("status", status_filter.value)
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    rows = result.data or []
    workers = service.worker_cards([r["worker_id"] for r in rows])
    for row in rows:
        row["worker"] = workers.get(row["worker_id"])
    return _page(result.count, rows, limit, offset)


_RESPONSES = {
    "accept": ("pending", "accepted", "Contact request accepted. This worker can now see your contact details."),
    "reject": ("pending", "rejected", "Contact request rejected."),
    "revoke": ("accepted", "revoked", "Contact access withdrawn. This worker can no longer see your contact details."),
}


@router.post("/contact-requests/{request_id}/respond")
def respond_to_contact_request(request_id: UUID, payload: ContactRequestRespond, user=Depends(get_current_employer)):
    """Only the employer the request was sent to can accept, reject or revoke it."""
    me = str(user.id)
    required, new_status, message = _RESPONSES[payload.action]
    updated = (
        admin_db.table("employer_contact_requests")
        .update({"status": new_status, "responded_at": service.now_iso()})
        .eq("id", str(request_id)).eq("employer_id", me).eq("status", required)
        .execute()
    ).data
    if not updated:
        raise _diagnose_failed_update(request_id, "employer_id", me)
    return {"message": message, "request": updated[0]}