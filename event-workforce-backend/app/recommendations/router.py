"""Recommendations module.

  GET /jobs/{job_id}/related    worker only

Jobs related to the one the worker opened: same category, open, not past, not the
same job, and within 20 km of the worker's preferred_area.
"""
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.applications.deps import get_current_worker   # reuse the shared worker check
from app.auth.db import admin_db
from app.auth.deps import get_current_user
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

@router.get("/recommendations/home")
def worker_home_recommendations(
    city: str | None = None,
    area: str | None = None,
    skill_id: int | None = Query(None, ge=1),
    sort_by: Literal["recent", "upcoming"] = "recent",
    user=Depends(get_current_user),
):
    """Return separate home-feed sections based on worker skills, location and experience."""
    user_id = str(user.id)
    profile_rows = (
        admin_db.table("profiles")
        .select("role, role_selected")
        .eq("id", user_id)
        .limit(1)
        .execute()
    ).data or []
    if not profile_rows or profile_rows[0].get("role") != "worker" or not profile_rows[0].get("role_selected"):
        raise HTTPException(status_code=403, detail="Worker account access is required.")

    worker_rows = (
        admin_db.table("worker_profiles")
        .select("preferred_state, preferred_district, preferred_area, experience_level")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data or []
    worker = worker_rows[0] if worker_rows else {}

    selected_rows = (
        admin_db.table("worker_profile_skills")
        .select("skill_id")
        .eq("user_id", user_id)
        .execute()
    ).data or []
    skill_ids = sorted({int(row["skill_id"]) for row in selected_rows})
    skills = []
    if skill_ids:
        skills = (
            admin_db.table("skills")
            .select("id, name")
            .in_("id", skill_ids)
            .order("id")
            .execute()
        ).data or []
    if skill_id is not None:
        filter_skill = (
            admin_db.table("skills").select("id, name")
            .eq("id", skill_id).limit(1).execute()
        ).data or []
        if not filter_skill:
            raise HTTPException(status_code=422, detail="Choose a valid skill from the filter list.")
        skills = filter_skill

    query = (
        admin_db.table("jobs")
        .select(
            "id, title, category_id, description, job_date, reporting_time, "
            "start_time, end_time, workers_required, salary_per_worker, "
            "payment_type, venue_name, address, area, city, district, state, "
            "food_provided, transport_provided, dress_code, status, created_at, "
            "job_categories(name)"
        )
        .eq("status", JobStatus.open.value)
        .gte("job_date", today_ist().isoformat())
        .limit(300)
    )
    jobs = query.execute().data or []
    selected_city = (city or "").strip().lower()
    selected_area = (area or "").strip().lower()
    if selected_city:
        jobs = [job for job in jobs if selected_city in " ".join([
            str(job.get("city") or ""), str(job.get("district") or ""),
            str(job.get("state") or "")]).lower()]
    if selected_area:
        jobs = [job for job in jobs if selected_area in str(job.get("area") or "").lower()]
    if sort_by == "recent":
        jobs.sort(key=lambda job: str(job.get("created_at") or ""), reverse=True)
    else:
        jobs.sort(key=lambda job: (str(job.get("job_date") or ""), str(job.get("start_time") or "")))

    def searchable(job: dict) -> str:
        category = job.get("job_categories") or {}
        category_name = category.get("name", "") if isinstance(category, dict) else ""
        return " ".join([
            str(job.get("title") or ""),
            str(job.get("description") or ""),
            str(category_name),
        ]).lower()

    def score_for_skill(job: dict, skill_name: str) -> int:
        text = searchable(job)
        needle = skill_name.lower().strip()
        if not needle:
            return 0
        if needle in text:
            return 100
        tokens = [token for token in needle.split() if len(token) > 2]
        return sum(15 for token in tokens if token in text)

    if skill_id is not None and skills:
        selected_skill_name = str(skills[0].get("name") or "")
        jobs = [job for job in jobs if score_for_skill(job, selected_skill_name) > 0]

    skill_sections = []
    for skill in skills:
        matching = [
            job for job in jobs
            if score_for_skill(job, str(skill.get("name") or "")) > 0
        ]
        matching.sort(
            key=lambda job: str(job.get("created_at") or "") if sort_by == "recent" else str(job.get("job_date") or ""),
            reverse=(sort_by == "recent"),
        )
        matching.sort(
            key=lambda job: score_for_skill(job, str(skill.get("name") or "")),
            reverse=True,
        )
        if matching:
            skill_sections.append({
                "skill_id": skill["id"],
                "title": f"{skill['name']} jobs",
                "items": matching[:12],
            })

    preferred_area = str(worker.get("preferred_area") or "").strip()
    preferred_district = str(worker.get("preferred_district") or "").strip()
    preferred_city = str(worker.get("preferred_state") or "").strip()
    location_terms = [value.lower() for value in (preferred_area, preferred_district) if value]
    location_jobs = [
        job for job in jobs
        if any(
            term in " ".join([
                str(job.get("area") or ""),
                str(job.get("district") or ""),
                str(job.get("city") or ""),
            ]).lower()
            for term in location_terms
        )
    ]
    if not location_jobs and preferred_district:
        location_jobs = [
            job for job in jobs
            if preferred_district.lower() in str(job.get("city") or "").lower()
            or preferred_district.lower() in str(job.get("district") or "").lower()
        ]

    experience = str(worker.get("experience_level") or "fresher")
    experience_labels = {
        "fresher": "Fresher",
        "less_than_1_year": "Less than 1 year",
        "1_to_3_years": "1–3 years",
        "3_to_5_years": "3–5 years",
        "5_plus_years": "5+ years",
    }
    experience_keywords = (
        {"fresher", "entry", "trainee", "junior", "assistant", "general"}
        if experience in {"fresher", "less_than_1_year"}
        else {"supervisor", "senior", "lead", "manager"}
        if experience in {"3_to_5_years", "5_plus_years"}
        else {"assistant", "staff", "support", "executive"}
    )
    experience_jobs = [
        job for job in jobs
        if any(word in searchable(job) for word in experience_keywords)
    ]
    if not experience_jobs:
        experience_jobs = jobs[:]

    return {
        "filters": {"city": city or None, "area": area or None, "skill_id": skill_id, "sort_by": sort_by},
        "preferred_area": preferred_area or None,
        "preferred_city": preferred_district or None,
        "experience_level": experience,
        "experience_label": experience_labels.get(experience, experience.replace("_", " ").title()),
        "skills": skills,
        "sections": {
            "skills": skill_sections,
            "location": location_jobs[:20],
            "experience": experience_jobs[:20],
            "all_jobs": jobs[:30],
        },
    }
