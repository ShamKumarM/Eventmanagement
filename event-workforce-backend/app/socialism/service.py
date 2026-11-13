"""Shared public-card helpers for the unified socialism module."""
from app.auth.db import admin_db


def worker_cards(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    rows = (admin_db.table("profiles").select("id, full_name, avatar_url")
            .in_("id", ids).eq("role", "worker").eq("role_selected", True).execute()).data or []
    counts = (admin_db.table("worker_follower_counts")
              .select("worker_id, follower_count").in_("worker_id", ids).execute()).data or []
    count_map = {r["worker_id"]: r["follower_count"] for r in counts}
    return {r["id"]: {"id": r["id"], "full_name": r.get("full_name"),
                      "avatar_url": r.get("avatar_url"),
                      "follower_count": count_map.get(r["id"], 0)} for r in rows}


def employer_cards(ids: list[str], viewer_worker_id: str | None = None) -> list[dict]:
    if not ids:
        return []
    eps = (admin_db.table("employer_profiles")
           .select("user_id, organisation_name, description, business_type, business_area, years_in_business, website_url, logo_url, verification_status")
           .in_("user_id", ids).execute()).data or []
    profs = (admin_db.table("profiles").select("id, avatar_url, role, role_selected")
             .in_("id", ids).execute()).data or []
    valid = {p["id"]: p for p in profs if p.get("role") == "employer" and p.get("role_selected")}
    counts_rows = (admin_db.table("employer_follower_counts")
                   .select("employer_id, follower_count").in_("employer_id", ids).execute()).data or []
    counts = {r["employer_id"]: r["follower_count"] for r in counts_rows}
    follows = set()
    if viewer_worker_id:
        follows = {r["employer_id"] for r in (
            admin_db.table("employer_follows").select("employer_id")
            .eq("worker_id", viewer_worker_id).in_("employer_id", ids).execute()).data or []}
    by_id = {e["user_id"]: e for e in eps}
    result = []
    for eid in ids:
        e = by_id.get(eid)
        if not e or eid not in valid:
            continue
        result.append({
            "id": eid, "organisation_name": e.get("organisation_name"),
            "description": e.get("description"), "business_type": e.get("business_type"),
            "business_area": e.get("business_area"), "years_in_business": e.get("years_in_business"),
            "website_url": e.get("website_url"), "logo_url": e.get("logo_url"),
            "avatar_url": valid[eid].get("avatar_url"),
            "verified": e.get("verification_status") == "approved",
            "follower_count": counts.get(eid, 0),
            "is_following": eid in follows if viewer_worker_id else False,
        })
    return result
