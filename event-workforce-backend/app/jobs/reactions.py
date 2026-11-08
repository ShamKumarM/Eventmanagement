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
