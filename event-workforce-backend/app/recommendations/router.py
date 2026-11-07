"""Recommendations module.

  GET /jobs/{job_id}/related    worker only

Jobs related to the one the worker opened: same category, open, not past, not the
same job, and within 20 km of the worker's preferred_area.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.applications.deps import get_current_worker   # reuse the shared worker check
from app.auth.db import admin_db
from app.jobs.schemas import JobStatus, today_ist

from .geo import RADIUS_KM, rank_nearby, resolve_area

router = APIRouter(tags=["recommendations"])

JOB_COLUMNS = (
    "id, title, category_id, job_date, start_time, end_time, workers_required, "
    "salary_per_worker, payment_type, area, city, latitude, longitude"
)
CANDIDATE_LIMIT = 200   # MVP: filter by distance in Python; move to SQL if the table grows large


@router.get("/jobs/{job_id}/related")
def related_jobs(
    job_id: UUID,
    limit: int = Query(10, ge=1, le=20),
    ctx=Depends(get_current_worker),
):
    user_id = str(ctx["user"].id)

    opened = (
        admin_db.table("jobs").select("id, category_id, status")
        .eq("id", str(job_id)).limit(1).execute()
    ).data
    if not opened or opened[0]["status"] == JobStatus.draft.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    category_id = opened[0]["category_id"]

    base = {"job_id": str(job_id), "category_id": category_id, "radius_km": RADIUS_KM}

    wp = (
        admin_db.table("worker_profiles").select("preferred_area")
        .eq("user_id", user_id).limit(1).execute()
    ).data
    area = (wp[0].get("preferred_area") if wp else None) or ""
    origin = resolve_area(area)
    if origin is None:
        note = (
            "Set your preferred area in your profile to see nearby jobs."
            if not area.strip()
            else f"We don't have a location for '{area}' yet, so nearby jobs can't be shown."
        )
        return {**base, "worker_location": None, "total": 0, "items": [], "note": note}

    candidates = (
        admin_db.table("jobs").select(JOB_COLUMNS)
        .eq("category_id", category_id)
        .eq("status", JobStatus.open.value)
        .gte("job_date", today_ist().isoformat())
        .neq("id", str(job_id))
        .order("job_date").limit(CANDIDATE_LIMIT).execute()
    ).data or []

    items = rank_nearby(candidates, origin, RADIUS_KM)[:limit]

    applied = set()
    if items:
        rows = (
            admin_db.table("applications").select("job_id")
            .eq("worker_id", user_id).in_("job_id", [i["id"] for i in items]).execute()
        ).data or []
        applied = {r["job_id"] for r in rows}
    for item in items:
        item["already_applied"] = item["id"] in applied

    return {
        **base,
        "worker_location": {"area": area, "latitude": origin[0], "longitude": origin[1]},
        "total": len(items),
        "items": items,
    }