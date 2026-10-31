import json
from datetime import date, datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from .db import db
from .deps import get_current_employer, get_current_user
from .schemas import (
    JOB_FIELDS,
    JobCreate,
    JobStatus,
    JobUpdate,
    TimeOfDay,
    today_ist,
)

router = APIRouter(tags=["jobs"])

SELECT = "*, job_categories(name)"
EDITABLE = {JobStatus.draft.value, JobStatus.open.value}
CANCELLABLE = {JobStatus.draft.value, JobStatus.open.value, JobStatus.filled.value}

TIME_BUCKETS = {
    TimeOfDay.morning: ["and(start_time.gte.05:00:00,start_time.lt.12:00:00)"],
    TimeOfDay.afternoon: ["and(start_time.gte.12:00:00,start_time.lt.16:00:00)"],
    TimeOfDay.evening: ["and(start_time.gte.16:00:00,start_time.lt.21:00:00)"],
    TimeOfDay.night: ["start_time.gte.21:00:00", "start_time.lt.05:00:00"],
}


# ---------- helpers ----------

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def selected_counts(job_ids: list[str]) -> dict[str, int]:
    """Number of selected workers per job.

    TODO: wire to the applications table once it exists, e.g.
      db.table("applications").select("job_id").in_("job_id", job_ids)
        .eq("status", "selected").execute()
    """
    return {}


def with_positions(rows: list[dict]) -> list[dict]:
    counts = selected_counts([r["id"] for r in rows])
    for r in rows:
        filled = counts.get(r["id"], 0)
        r["positions_filled"] = filled
        r["positions_left"] = max(r["workers_required"] - filled, 0)
    return rows


def get_job_or_404(job_id: UUID) -> dict:
    res = db.table("jobs").select(SELECT).eq("id", str(job_id)).execute()
    if not res.data:
        raise HTTPException(404, "Job not found")
    return res.data[0]


def require_owner(job: dict, user) -> None:
    if job["employer_id"] != str(user.id):
        raise HTTPException(403, "Not your job")


def check_category(category_id: int) -> None:
    res = (
        db.table("job_categories").select("id")
        .eq("id", category_id).eq("is_active", True).execute()
    )
    if not res.data:
        raise HTTPException(422, "Invalid category_id")


def weekend_range(today: date) -> tuple[date, date]:
    wd = today.weekday()  # Mon=0 ... Sat=5, Sun=6
    if wd == 6:
        return today, today
    if wd == 5:
        return today, today + timedelta(days=1)
    sat = today + timedelta(days=5 - wd)
    return sat, sat + timedelta(days=1)


# ---------- categories ----------

@router.get("/categories")
def list_categories(user=Depends(get_current_user)):
    res = (
        db.table("job_categories").select("id, name")
        .eq("is_active", True).order("id").execute()
    )
    return res.data


# ---------- employer side ----------

@router.post("/jobs", status_code=201)
def create_job(payload: JobCreate, user=Depends(get_current_employer)):
    check_category(payload.category_id)
    row = payload.model_dump(mode="json")
    row.update(employer_id=str(user.id), status=JobStatus.open.value)
    res = db.table("jobs").insert(row).execute()
    job = res.data[0]
    # TODO: emit "job created" event -> notify workers whose preferences match.
    return job


@router.get("/jobs/mine")
def my_jobs(
    status: Optional[JobStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user=Depends(get_current_employer),
):
    q = db.table("jobs").select(SELECT, count="exact").eq("employer_id", str(user.id))
    if status:
        q = q.eq("status", status.value)
    start = (page - 1) * page_size
    res = q.order("job_date", desc=True).range(start, start + page_size - 1).execute()
    return {"total": res.count, "page": page, "items": with_positions(res.data)}


@router.patch("/jobs/{job_id}")
def update_job(job_id: UUID, payload: JobUpdate, user=Depends(get_current_employer)):
    job = get_job_or_404(job_id)
    require_owner(job, user)
    if job["status"] not in EDITABLE:
        raise HTTPException(409, f"Cannot edit a job that is {job['status']}")

    patch = payload.model_dump(exclude_unset=True, mode="json")
    if not patch:
        raise HTTPException(422, "No fields to update")

    merged = {k: job[k] for k in JOB_FIELDS} | {
        k: v for k, v in payload.model_dump(exclude_unset=True).items()
    }
    try:
        JobCreate(**merged)  # re-run every validation on the final state
    except ValidationError as e:
        raise HTTPException(422, detail=json.loads(e.json(include_url=False)))

    if "category_id" in patch:
        check_category(patch["category_id"])

    if "workers_required" in patch:
        selected = selected_counts([job["id"]]).get(job["id"], 0)
        if patch["workers_required"] < selected:
            raise HTTPException(409, f"{selected} workers already selected")

    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = db.table("jobs").update(patch).eq("id", str(job_id)).execute()
    # TODO: if date/time/location changed, notify selected workers.
    return res.data[0]


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: UUID, user=Depends(get_current_employer)):
    job = get_job_or_404(job_id)
    require_owner(job, user)
    if job["status"] not in CANCELLABLE:
        raise HTTPException(409, f"Cannot cancel a job that is {job['status']}")
    res = (
        db.table("jobs")
        .update({
            "status": JobStatus.cancelled.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", str(job_id)).execute()
    )
    # TODO: notify selected workers ("Job cancellation").
    return res.data[0]


# ---------- worker side ----------

@router.get("/jobs")
def job_feed(
    category_id: Optional[list[int]] = Query(None),
    city: Optional[str] = None,
    area: Optional[str] = None,
    date_filter: Optional[Literal["today", "tomorrow", "weekend"]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_salary: Optional[float] = Query(None, ge=0),
    max_salary: Optional[float] = Query(None, ge=0),
    time_of_day: Optional[list[TimeOfDay]] = Query(None),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user=Depends(get_current_user),
):
    today = today_ist()

    # date window
    if date_filter == "today":
        lo = hi = today
    elif date_filter == "tomorrow":
        lo = hi = today + timedelta(days=1)
    elif date_filter == "weekend":
        lo, hi = weekend_range(today)
    else:
        lo, hi = max(date_from or today, today), date_to

    q = (
        db.table("jobs").select(SELECT, count="exact")
        .eq("status", JobStatus.open.value)
        .gte("job_date", lo.isoformat())
    )
    if hi:
        q = q.lte("job_date", hi.isoformat())
    if category_id:
        q = q.in_("category_id", category_id)
    if city:
        q = q.ilike("city", city)
    if area:
        q = q.ilike("area", area)
    if min_salary is not None:
        q = q.gte("salary_per_worker", min_salary)
    if max_salary is not None:
        q = q.lte("salary_per_worker", max_salary)
    if time_of_day:
        parts = [p for t in time_of_day for p in TIME_BUCKETS[t]]
        q = q.or_(",".join(parts))

    q = q.order("job_date").order("start_time")
    start = (page - 1) * page_size

    # distance filter: bounding box in SQL, exact Haversine in Python
    if lat is not None and lng is not None and radius_km:
        dlat = radius_km / 111.0
        dlng = radius_km / (111.0 * max(cos(radians(lat)), 0.01))
        q = (
            q.gte("latitude", lat - dlat).lte("latitude", lat + dlat)
            .gte("longitude", lng - dlng).lte("longitude", lng + dlng)
        )
        rows = q.limit(500).execute().data
        for r in rows:
            r["distance_km"] = round(haversine_km(lat, lng, r["latitude"], r["longitude"]), 1)
        rows = [r for r in rows if r["distance_km"] <= radius_km]
        total = len(rows)
        rows = rows[start:start + page_size]
    else:
        res = q.range(start, start + page_size - 1).execute()
        rows, total = res.data, res.count

    return {"total": total, "page": page, "items": with_positions(rows)}


@router.get("/jobs/{job_id}")
def job_detail(job_id: UUID, user=Depends(get_current_user)):
    job = get_job_or_404(job_id)
    if job["status"] == JobStatus.draft.value and job["employer_id"] != str(user.id):
        raise HTTPException(404, "Job not found")
    return with_positions([job])[0]
