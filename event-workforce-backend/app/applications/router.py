"""Job Applications module.

Endpoints
  POST  /applications                      worker   apply to a job
  GET   /applications/mine                 worker   my applications
  POST  /applications/{id}/withdraw        worker   withdraw my application
  GET   /jobs/{job_id}/applications        employer applicants for my job
  PATCH /applications/{id}/status          employer accept / reject
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.auth.db import admin_db
from app.jobs.schemas import JobStatus, today_ist
from app.jobs.expiry import job_is_expired
from app.notifications.service import create_notification

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
JOB_COLUMNS = (
    "id, employer_id, title, job_date, reporting_time, start_time, end_time, area, city, salary_per_worker, "
    "workers_required, male_required, female_required, trans_required, status"
)


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
    if job_is_expired(job):
        raise HTTPException(status.HTTP_409_CONFLICT, "This job has expired and is no longer accepting applications.")

    # Gender-allocated postings only accept applicants for a remaining gender slot.
    gender_counts = (job.get("male_required"), job.get("female_required"), job.get("trans_required"))
    if any(value is not None for value in gender_counts):
        worker_gender = profile.get("gender")
        if worker_gender not in {"male", "female", "trans"}:
            raise HTTPException(status.HTTP_409_CONFLICT, "Set your gender in your profile before applying to this job.")
        quota_column = {"male": "male_required", "female": "female_required", "trans": "trans_required"}[worker_gender]
        quota = job.get(quota_column) or 0
        selected_rows = (
            admin_db.table("applications").select("worker_id")
            .eq("job_id", str(payload.job_id)).eq("status", "selected").execute()
        ).data or []
        selected_ids = [row["worker_id"] for row in selected_rows]
        selected_for_gender = 0
        if selected_ids:
            gender_rows = (
                admin_db.table("profiles").select("id")
                .eq("gender", worker_gender).in_("id", selected_ids).execute()
            ).data or []
            selected_for_gender = len(gender_rows)
        if quota <= selected_for_gender:
            raise HTTPException(status.HTTP_409_CONFLICT, f"No {worker_gender} positions remain for this job.")

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
        admin_db.table("applications").select("*")
        .eq("worker_id", str(ctx["user"].id))
    )
    if status_filter:
        q = q.eq("status", status_filter.value)
    res = q.order("created_at", desc=True).execute()
    rows = res.data or []

    jobs = {}
    if rows:
        job_rows = (
            admin_db.table("jobs").select(
                "id, employer_id, title, category_id, job_categories(name), description, job_date, "
                "reporting_time, start_time, end_time, area, district, city, state, "
                "venue_name, address, salary_per_worker, workers_required, "
                "food_provided, transport_provided, dress_code, status"
            ).in_("id", list({r["job_id"] for r in rows})).execute().data
        )
        jobs = {j["id"]: j for j in job_rows}
    # Hide applications for jobs whose scheduled shift has ended, even if the
    # daily Supabase cleanup has not run yet.
    rows = [
        row for row in rows
        if jobs.get(row["job_id"]) and not job_is_expired(jobs[row["job_id"]])
    ]
    total = len(rows)
    start = (page - 1) * page_size
    rows = rows[start:start + page_size]
    # Employer contact details are private until the employer selects this worker.
    selected_employer_ids = list({
        jobs[r["job_id"]]["employer_id"]
        for r in rows
        if r.get("status") == ApplicationStatus.selected.value
        and jobs.get(r["job_id"], {}).get("employer_id")
    })
    employer_contacts = {}
    if selected_employer_ids:
        profiles = (admin_db.table("profiles").select("id, phone")
                    .in_("id", selected_employer_ids).execute()).data or []
        employer_profiles = (admin_db.table("employer_profiles")
                    .select("user_id, organisation_name, contact_person")
                    .in_("user_id", selected_employer_ids).execute()).data or []
        shared_by_id = {p["id"]: p for p in profiles}
        employer_by_id = {p["user_id"]: p for p in employer_profiles}
        for employer_id in selected_employer_ids:
            email = None
            try:
                auth_result = admin_db.auth.admin.get_user_by_id(employer_id)
                auth_user = getattr(auth_result, "user", None)
                email = getattr(auth_user, "email", None) if auth_user else None
            except Exception:
                email = None
            shared = shared_by_id.get(employer_id, {})
            employer = employer_by_id.get(employer_id, {})
            employer_contacts[employer_id] = {
                "mobile": shared.get("phone"),
                "email": email,
                "organisation_name": employer.get("organisation_name"),
                "contact_person": employer.get("contact_person"),
            }

    for r in rows:
        r["job"] = jobs.get(r["job_id"])
        r["employer_contact"] = (
            employer_contacts.get(r["job"].get("employer_id"))
            if r.get("status") == ApplicationStatus.selected.value and r["job"]
            else None
        )
    return {"total": total, "page": page, "items": rows}


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
            .select("id, full_name, phone, gender, avatar_url")
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
                "gender": p.get("gender"),
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
    if job["status"] in LOCKED_JOB_STATUSES or job_is_expired(job):
        raise HTTPException(status.HTTP_409_CONFLICT, "This job has expired or closed; applications can no longer be changed.")

    current, new = ApplicationStatus(app["status"]), payload.status
    if current == ApplicationStatus.shortlisted:
        # Legacy shortlisted records can still be accepted or rejected.
        allowed = {ApplicationStatus.selected, ApplicationStatus.rejected}
    elif current == ApplicationStatus.pending:
        allowed = {ApplicationStatus.selected, ApplicationStatus.rejected}
    else:
        allowed = set()
    if new not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot change status from {current.value} to {new.value}.")

    if new == ApplicationStatus.selected:
        # Enforce the allocated gender quota in addition to the overall job capacity.
        gender_counts = (job.get("male_required"), job.get("female_required"), job.get("trans_required"))
        if any(value is not None for value in gender_counts):
            applicant_profile = (
                admin_db.table("profiles").select("gender")
                .eq("id", app["worker_id"]).limit(1).execute().data or []
            )
            applicant_gender = applicant_profile[0].get("gender") if applicant_profile else None
            quota_column = {"male": "male_required", "female": "female_required", "trans": "trans_required"}.get(applicant_gender)
            if quota_column is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "Applicant must have a valid gender in their profile.")
            quota = int(job.get(quota_column) or 0)
            selected_rows = (
                admin_db.table("applications").select("worker_id")
                .eq("job_id", app["job_id"]).eq("status", ApplicationStatus.selected.value).execute()
            ).data or []
            selected_ids = [row["worker_id"] for row in selected_rows]
            already_selected_gender = 0
            if selected_ids:
                gender_rows = (
                    admin_db.table("profiles").select("id")
                    .eq("gender", applicant_gender).in_("id", selected_ids).execute()
                ).data or []
                already_selected_gender = len(gender_rows)
            if already_selected_gender >= quota:
                raise HTTPException(status.HTTP_409_CONFLICT, f"The {applicant_gender} positions for this job are already filled.")

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
    if new == ApplicationStatus.selected and current != ApplicationStatus.selected:
        create_notification(
            str(app["worker_id"]),
            "application_accepted",
            "Your application was accepted!",
            f"The employer selected you for {job.get('title') or 'an event job'}. "
            "Open My Applications to view the employer's contact details.",
            {"application_id": str(application_id), "job_id": str(app["job_id"]),
             "job_title": job.get("title")},
        )
    return res.data[0]