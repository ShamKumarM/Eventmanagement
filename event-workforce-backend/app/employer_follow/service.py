"""Query helpers shared by the employer follow routes.

PRIVACY DESIGN
  * Public views (cards) select ONLY public columns. Private columns are never read there,
    so they cannot leak by accident.
  * release_contact() is the single place that reads private contact data, and the router
    calls it only after confirming an ACCEPTED contact request for that exact worker/employer pair.

POPULARITY vs VERIFICATION
  * follower_count / most_followed come only from employer_follows.
  * verified comes only from employer_profiles.verification_status == "approved" (set by admins).
  * Neither value is derived from the other.
"""
import logging
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.auth.db import admin_db

logger = logging.getLogger(__name__)

# ---- tunable rules -------------------------------------------------------------------------
MOST_FOLLOWED_TOP_N = 10          # the "Most Followed" badge goes to the top N employers...
MOST_FOLLOWED_MIN_FOLLOWERS = 3   # ...that also have at least this many followers.

# Private contact data: read ONLY by release_contact().
PRIVATE_FIELDS = ("phone", "email", "contact_person", "business_address")

_PUBLIC_EMPLOYER_COLUMNS = (
    "user_id, organisation_name, description, business_type, business_area, "
    "years_in_business, website_url, logo_url, verification_status"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def like_pattern(text: str) -> str:
    """Escape LIKE wildcards so a search for '50%' searches for the text, not a wildcard."""
    return "%" + re.sub(r"([\\%_])", r"\\\1", text.strip()) + "%"


# ---- employers -----------------------------------------------------------------------------
def active_employers(ids: list[str]) -> dict[str, dict]:
    """employer_id -> public employer data, only for accounts that really are selected employers."""
    if not ids:
        return {}
    employers = (
        admin_db.table("employer_profiles").select(_PUBLIC_EMPLOYER_COLUMNS).in_("user_id", ids).execute()
    ).data or []
    profiles = (
        admin_db.table("profiles").select("id, avatar_url, role, role_selected").in_("id", ids).execute()
    ).data or []
    ok = {p["id"]: p for p in profiles if p.get("role") == "employer" and p.get("role_selected")}
    return {
        e["user_id"]: {**e, "avatar_url": ok[e["user_id"]].get("avatar_url")}
        for e in employers
        if e["user_id"] in ok
    }


def require_employer(employer_id: str) -> dict:
    found = active_employers([employer_id]).get(employer_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer not found.")
    return found


def follower_counts(ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    rows = (
        admin_db.table("employer_follower_counts").select("employer_id, follower_count").in_("employer_id", ids).execute()
    ).data or []
    return {r["employer_id"]: r["follower_count"] for r in rows}


def follower_count(employer_id: str) -> int:
    return follower_counts([employer_id]).get(employer_id, 0)


def most_followed_ids() -> set[str]:
    rows = (
        admin_db.table("employer_follower_counts")
        .select("employer_id")
        .gte("follower_count", MOST_FOLLOWED_MIN_FOLLOWERS)
        .order("follower_count", desc=True)
        .order("employer_id")
        .limit(MOST_FOLLOWED_TOP_N)
        .execute()
    ).data or []
    return {r["employer_id"] for r in rows}


# ---- worker-specific state -----------------------------------------------------------------
def following_set(worker_id: str, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    rows = (
        admin_db.table("employer_follows").select("employer_id").eq("worker_id", worker_id).in_("employer_id", ids).execute()
    ).data or []
    return {r["employer_id"] for r in rows}


def contact_states(worker_id: str, ids: list[str]) -> dict[str, tuple[str, str]]:
    """employer_id -> (latest request status, request id) for this worker."""
    if not ids:
        return {}
    rows = (
        admin_db.table("employer_contact_requests")
        .select("id, employer_id, status, created_at")
        .eq("worker_id", worker_id)
        .in_("employer_id", ids)
        .order("created_at", desc=True)
        .execute()
    ).data or []
    states: dict[str, tuple[str, str]] = {}
    for row in rows:                       # newest first, so the first row per employer wins
        states.setdefault(row["employer_id"], (row["status"], row["id"]))
    return states


def contact_status(worker_id: str, employer_id: str) -> str:
    state = contact_states(worker_id, [employer_id]).get(employer_id)
    return state[0] if state else "none"


# ---- public cards --------------------------------------------------------------------------
def build_cards(ids: list[str], viewer_worker_id: str | None = None) -> list[dict]:
    """Public employer cards in the given order. Contains NO private contact data."""
    employers = active_employers(ids)
    counts = follower_counts(list(employers))
    badge_ids = most_followed_ids()
    following = following_set(viewer_worker_id, list(employers)) if viewer_worker_id else set()
    states = contact_states(viewer_worker_id, list(employers)) if viewer_worker_id else {}

    cards = []
    for employer_id in ids:
        e = employers.get(employer_id)
        if not e:
            continue
        card = {
            "id": employer_id,
            "organisation_name": e.get("organisation_name"),
            "description": e.get("description"),
            "business_type": e.get("business_type"),
            "business_area": e.get("business_area"),
            "years_in_business": e.get("years_in_business"),
            "website_url": e.get("website_url"),
            "logo_url": e.get("logo_url"),
            "avatar_url": e.get("avatar_url"),
            # Blue tick: ONLY an admin-approved verification, regardless of followers.
            "verified": e.get("verification_status") == "approved",
            # Popularity: follower count only, regardless of verification.
            "follower_count": counts.get(employer_id, 0),
            "most_followed": employer_id in badge_ids,
        }
        if viewer_worker_id:
            state = states.get(employer_id)
            card["is_following"] = employer_id in following
            card["contact_access"] = {
                "status": state[0] if state else "none",
                "request_id": state[1] if state else None,
            }
        cards.append(card)
    return cards


def mini_employer_cards(ids: list[str]) -> dict[str, dict]:
    """Small employer summary used inside contact-request lists."""
    employers = active_employers(ids)
    return {
        eid: {
            "id": eid,
            "organisation_name": e.get("organisation_name"),
            "logo_url": e.get("logo_url"),
            "verified": e.get("verification_status") == "approved",
        }
        for eid, e in employers.items()
    }


def worker_cards(ids: list[str]) -> dict[str, dict]:
    """Worker name + photo only. Never a phone number or email."""
    if not ids:
        return {}
    rows = (
        admin_db.table("profiles").select("id, full_name, avatar_url").in_("id", ids).eq("role", "worker").execute()
    ).data or []
    return {r["id"]: {"id": r["id"], "full_name": r.get("full_name"), "avatar_url": r.get("avatar_url")} for r in rows}


# ---- the only place private contact details are read --------------------------------------
def _employer_email(employer_id: str) -> str | None:
    try:
        return admin_db.auth.admin.get_user_by_id(employer_id).user.email
    except Exception:
        logger.exception("Could not load employer email for %s", employer_id)
        return None


def release_contact(employer_id: str) -> dict:
    """Return private contact details. CALL ONLY after an accepted request has been confirmed."""
    profile = (
        admin_db.table("profiles").select("phone").eq("id", employer_id).limit(1).execute()
    ).data or [{}]
    employer = (
        admin_db.table("employer_profiles").select("contact_person, business_address").eq("user_id", employer_id).limit(1).execute()
    ).data or [{}]
    return {
        "phone": profile[0].get("phone"),
        "email": _employer_email(employer_id),
        "contact_person": employer[0].get("contact_person"),
        "business_address": employer[0].get("business_address"),
    }