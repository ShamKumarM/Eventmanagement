"""Job Applications module.

Endpoints
  POST  /applications                      worker   apply to a job
  GET   /applications/mine                 worker   my applications
  POST  /applications/{id}/withdraw        worker   withdraw my application
  GET   /jobs/{job_id}/applications        employer applicants for my job
  PATCH /applications/{id}/status          employer shortlist / select / reject
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.auth.db import admin_db
from app.jobs.schemas import JobStatus, today_ist

from .deps import assert_worker_eligible, get_current_employer, get_current_worker
from .schemas import (
    EMPLOYER_TRANSITIONS,
    WORKER_WITHDRAWABLE,
    ApplicationCreate,
    ApplicationStatus,
    ApplicationStatusUpdate,
)

router = APIRouter(tags=["applications"])

# Jobs the employer can no longer change applications for.
LOCKED_JOB_STATUSES = {
    JobStatus.cancelled.value, JobStatus.completed.value, JobStatus.expired.value,
}
JOB_COLUMNS = "id, employer_id, title, job_date, start_time, area, city, salary_per_worker, workers_required, status"


# ---------- helpers ----------

def _get_job(job_id) -> dict:
    res = admin_db.table("jobs").select(JOB_COLUMNS).eq("id", str(job_id)).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return res.data[0]


def _get_application(application_id: UUID) -> dict:
    res = admin_db.table("applications").select("*").eq("id", str(application_id)).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found.")
    return res.data[0]


def _paginate(page: int, page_size: int) -> tuple[int, int]:
    start = (page - 1) * page_size
    return start, start + page_size - 1


# ---------- worker ----------

@router.post("/applications", status_code=status.HTTP_201_CREATED)
def apply_to_job(payload: ApplicationCreate, ctx=Depends(get_current_worker)):
    user, profile = ctx["user"], ctx["profile"]
    job = _get_job(payload.job_id)

    # Rule 6: same rule the job feed uses: status open and date not past (IST).
    if job["status"] != JobStatus.open.value:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This job is not open for applications (status: {job['status']}).")
    if job["job_date"] < today_ist().isoformat():
        raise HTTPException(status.HTTP_409_CONFLICT, "This job's date has already passed.")

    # Rule 5: agreed profile-completion rule.
    assert_worker_eligible(str(user.id), profile)

    try:
        res = admin_db.table("applications").insert({
            "job_id": str(payload.job_id),
            "worker_id": str(user.id),          # Rule 9: from the token, never the body
            "cover_note": payload.cover_note,
        }).execute()
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":   # unique (job_id, worker_id)
            raise HTTPException(status.HTTP_409_CONFLICT, "You have already applied to this job.") from exc
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not submit your application.") from exc
    return res.data[0]


@router.get("/applications/mine")
def my_applications(
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ctx=Depends(get_current_worker),
):
    q = (
        admin_db.table("applications").select("*", count="exact")
        .eq("worker_id", str(ctx["user"].id))
    )
    if status_filter:
        q = q.eq("status", status_filter.value)
    lo, hi = _paginate(page, page_size)
    res = q.order("created_at", desc=True).range(lo, hi).execute()
    rows = res.data or []

    jobs = {}
    if rows:
        job_rows = (
            admin_db.table("jobs").select(
                "id, title, category_id, job_categories(name), description, job_date, "
                "reporting_time, start_time, end_time, area, district, city, state, "
                "venue_name, address, salary_per_worker, workers_required, "
                "food_provided, transport_provided, dress_code, status"
            ).in_("id", list({r["job_id"] for r in rows})).execute().data
        )
        jobs = {j["id"]: j for j in job_rows}
    for r in rows:
        r["job"] = jobs.get(r["job_id"])
    return {"total": res.count, "page": page, "items": rows}


@router.post("/applications/{application_id}/withdraw")
def withdraw_application(application_id: UUID, ctx=Depends(get_current_worker)):
    app = _get_application(application_id)
    if app["worker_id"] != str(ctx["user"].id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your application.")
    if ApplicationStatus(app["status"]) not in WORKER_WITHDRAWABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot withdraw an application that is {app['status']}.")
    res = (
        admin_db.table("applications").update({"status": ApplicationStatus.withdrawn.value})
        .eq("id", str(application_id)).execute()
    )
    return res.data[0]


# ---------- employer ----------

@router.get("/jobs/{job_id}/applications")
def applications_for_job(
    job_id: UUID,
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user=Depends(get_current_employer),
):
    job = _get_job(job_id)
    if job["employer_id"] != str(user.id):           # Rule 9: ownership check
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your job.")

    q = admin_db.table("applications").select("*", count="exact").eq("job_id", str(job_id))
    if status_filter:
        q = q.eq("status", status_filter.value)
    lo, hi = _paginate(page, page_size)
    res = q.order("created_at").range(lo, hi).execute()
    rows = res.data or []

    # Attach applicant details (columns confirmed from the Profile module).
    if rows:
        ids = [r["worker_id"] for r in rows]
        people = {
            p["id"]: p
            for p in admin_db.table("profiles")
            .select("id, full_name, phone, avatar_url")
            .in_("id", ids).execute().data
        }
        wp = {
            w["user_id"]: w
            for w in admin_db.table("worker_profiles")
            .select("user_id, bio, preferred_state, preferred_district, preferred_area, experience_level")
            .in_("user_id", ids).execute().data
        }
        skill_links = (
            admin_db.table("worker_profile_skills")
            .select("user_id, skill_id")
            .in_("user_id", ids).execute().data
        )
        skill_ids_by_user = {}
        for link in skill_links:
            skill_ids_by_user.setdefault(link["user_id"], []).append(link["skill_id"])
        all_skill_ids = sorted({sid for values in skill_ids_by_user.values() for sid in values})
        skill_names = {}
        if all_skill_ids:
            skill_names = {
                item["id"]: item["name"]
                for item in admin_db.table("skills").select("id, name")
                .in_("id", all_skill_ids).execute().data
            }
        for r in rows:
            p, w = people.get(r["worker_id"], {}), wp.get(r["worker_id"], {})
            r["applicant"] = {
                "full_name": p.get("full_name"),
                "phone": p.get("phone"),
                "avatar_url": p.get("avatar_url"),
                "bio": w.get("bio"),
                "preferred_state": w.get("preferred_state"),
                "preferred_district": w.get("preferred_district"),
                "preferred_area": w.get("preferred_area"),
                "experience_level": w.get("experience_level"),
                "skills": [
                    skill_names[sid]
                    for sid in skill_ids_by_user.get(r["worker_id"], [])
                    if sid in skill_names
                ],
            }
    return {"job_id": str(job_id), "total": res.count, "page": page, "items": rows}


@router.patch("/applications/{application_id}/status")
def update_application_status(
    application_id: UUID, payload: ApplicationStatusUpdate, user=Depends(get_current_employer)
):
    app = _get_application(application_id)
    job = _get_job(app["job_id"])
    if job["employer_id"] != str(user.id):           # Rule 9: ownership check
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your job.")
    if job["status"] in LOCKED_JOB_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Job is {job['status']}; applications can no longer be changed.")

    current, new = ApplicationStatus(app["status"]), payload.status
    if new not in EMPLOYER_TRANSITIONS.get(current, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot change status from {current.value} to {new.value}.")

    if new == ApplicationStatus.selected:
        # NOTE: check-then-update is not atomic; fine for MVP, use an RPC later if races appear.
        taken = (
            admin_db.table("applications").select("id", count="exact")
            .eq("job_id", app["job_id"]).eq("status", ApplicationStatus.selected.value).execute().count
        ) or 0
        if taken >= job["workers_required"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "All positions for this job are already filled.")

    res = (
        admin_db.table("applications").update({"status": new.value})
        .eq("id", str(application_id)).execute()
    )
    return res.data[0]