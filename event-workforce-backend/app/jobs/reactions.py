"""Shared job reaction helpers for feed and recommendation responses."""
from collections import defaultdict

from .db import db


def attach_reaction_counts(rows: list[dict], user_id: str | None = None) -> list[dict]:
    if not rows:
        return rows
    ids = [str(row["id"]) for row in rows if row.get("id")]
    if not ids:
        return rows
    try:
        reactions = (
            db.table("job_reactions")
            .select("job_id, user_id, vote")
            .in_("job_id", ids)
            .execute()
        ).data or []
    except Exception:
        # A missing migration should not take down the whole jobs feed.
        for row in rows:
            row.setdefault("likes_count", 0)
            row.setdefault("dislikes_count", 0)
            row.setdefault("my_reaction", None)
        return rows

    counts = defaultdict(lambda: {"likes": 0, "dislikes": 0})
    mine = {}
    for reaction in reactions:
        job_id = str(reaction.get("job_id"))
        vote = int(reaction.get("vote") or 0)
        if vote == 1:
            counts[job_id]["likes"] += 1
        elif vote == -1:
            counts[job_id]["dislikes"] += 1
        if user_id and str(reaction.get("user_id")) == user_id:
            mine[job_id] = vote

    for row in rows:
        job_id = str(row.get("id"))
        row["likes_count"] = counts[job_id]["likes"]
        row["dislikes_count"] = counts[job_id]["dislikes"]
        row["my_reaction"] = mine.get(job_id)
    return rows


def attach_employer_names(rows: list[dict]) -> list[dict]:
    """Add a human-readable employer name without exposing private profile data."""
    if not rows:
        return rows
    user_ids = sorted({str(row.get("employer_id")) for row in rows if row.get("employer_id")})
    if not user_ids:
        return rows
    names = {}
    try:
        org_rows = (
            db.table("employer_profiles")
            .select("user_id, organisation_name")
            .in_("user_id", user_ids)
            .execute()
        ).data or []
        for item in org_rows:
            if item.get("organisation_name"):
                names[str(item["user_id"])] = str(item["organisation_name"])
    except Exception:
        pass
    missing = [uid for uid in user_ids if uid not in names]
    if missing:
        try:
            profile_rows = (
                db.table("profiles")
                .select("id, full_name")
                .in_("id", missing)
                .execute()
            ).data or []
            for item in profile_rows:
                if item.get("full_name"):
                    names[str(item["id"])] = str(item["full_name"])
        except Exception:
            pass
    for row in rows:
        row["employer_name"] = names.get(str(row.get("employer_id")), "Verified event employer")
    return rows
