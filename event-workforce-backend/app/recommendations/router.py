"""Recommendations module.

  GET /jobs/{job_id}/related    worker only

Jobs related to the one the worker opened: same category, open, not past, not the
same job, and within 20 km of the worker's preferred_area.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.applications.deps import get_current_worker   # reuse the shared worker check
from app.auth.db import admin_db
from app.auth.deps import get_current_user
from app.jobs.schemas import JobStatus, today_ist
from app.jobs.reactions import attach_reaction_counts, attach_employer_names

from .geo import RADIUS_KM, rank_nearby, resolve_area
from .matching import build_top_picks

router = APIRouter(tags=["recommendations"])

JOB_COLUMNS = (
    "id, employer_id, title, category_id, job_date, start_time, end_time, workers_required, "
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

    attach_reaction_counts(items, user_id)
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
    skill: str | None = None,
    search: str | None = None,
    sort_by: str = Query("date", pattern="^(date|recent|pay)$"),
    user=Depends(get_current_user),
):
    """Return separate home-feed sections based on worker skills, location and experience."""
    user_id = str(user.id)
    profile_rows = (
        admin_db.table("profiles")
        .select("role, role_selected, gender")
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

    query = (
        admin_db.table("jobs")
        .select(
            "id, employer_id, title, category_id, description, job_date, reporting_time, "
            "start_time, end_time, workers_required, salary_per_worker, "
            "payment_type, venue_name, address, area, city, district, state, "
            "food_provided, transport_provided, dress_code, status, "
            "male_required, female_required, trans_required, "
            "job_categories(name)"
        )
        .eq("status", JobStatus.open.value)
        .gte("job_date", today_ist().isoformat())
        .limit(150)
    )
    selected_city = (city or "").strip()
    selected_area = (area or "").strip()
    if selected_city:
        query = query.ilike("city", f"%{selected_city}%")
    if selected_area:
        query = query.ilike("area", f"%{selected_area}%")
    if sort_by == "recent":
        query = query.order("created_at", desc=True)
    elif sort_by == "pay":
        query = query.order("salary_per_worker", desc=True)
    else:
        query = query.order("job_date")
    jobs = query.execute().data or []

    def searchable(job: dict) -> str:
        category = job.get("job_categories") or {}
        category_name = category.get("name", "") if isinstance(category, dict) else ""
        return " ".join([
            str(job.get("title") or ""),
            str(job.get("description") or ""),
            str(category_name),
            str(job.get("venue_name") or ""),
            str(job.get("area") or ""),
            str(job.get("district") or ""),
            str(job.get("city") or ""),
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

    requested_skill = (skill or "").strip().lower()
    if requested_skill:
        jobs = [job for job in jobs if requested_skill in searchable(job)]

    search_term = (search or "").strip().lower()
    if search_term:
        jobs = [job for job in jobs if search_term in searchable(job)]

    skill_sections = []
    for skill in skills:
        matching = [
            job for job in jobs
            if score_for_skill(job, str(skill.get("name") or "")) > 0
        ]
        matching.sort(
            key=lambda job: (
                -score_for_skill(job, str(skill.get("name") or "")),
                str(job.get("job_date") or ""),
            )
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

    worker_gender = profile_rows[0].get("gender")
    gender_jobs = []
    if worker_gender in {"male", "female", "trans"}:
        quota_column = {"male": "male_required", "female": "female_required", "trans": "trans_required"}[worker_gender]
        gender_jobs = [
            job for job in jobs
            if (
                # Legacy jobs with no gender allocation remain open to everyone.
                job.get("male_required") is None
                and job.get("female_required") is None
                and job.get("trans_required") is None
            ) or int(job.get(quota_column) or 0) > 0
        ]

    # Strict Top Picks: exact district, exact area, exact job-title/skill,
    # and remaining capacity for the worker's registered gender.
    selected_total_by_job: dict[str, int] = {}
    selected_gender_by_job: dict[str, dict[str, int]] = {}
    candidate_ids = [str(job["id"]) for job in jobs if job.get("id")]
    if candidate_ids:
        selected_applications = (
            admin_db.table("applications")
            .select("job_id, worker_id")
            .in_("job_id", candidate_ids)
            .eq("status", "selected")
            .execute()
        ).data or []
        selected_worker_ids = sorted({str(row["worker_id"]) for row in selected_applications if row.get("worker_id")})
        gender_by_worker: dict[str, str] = {}
        if selected_worker_ids:
            selected_profiles = (
                admin_db.table("profiles")
                .select("id, gender")
                .in_("id", selected_worker_ids)
                .execute()
            ).data or []
            gender_by_worker = {
                str(row["id"]): str(row.get("gender") or "").lower()
                for row in selected_profiles
            }
        for row in selected_applications:
            job_id = str(row.get("job_id") or "")
            worker_id = str(row.get("worker_id") or "")
            if not job_id:
                continue
            selected_total_by_job[job_id] = selected_total_by_job.get(job_id, 0) + 1
            selected_gender = gender_by_worker.get(worker_id)
            if selected_gender in {"male", "female", "trans"}:
                by_gender = selected_gender_by_job.setdefault(job_id, {})
                by_gender[selected_gender] = by_gender.get(selected_gender, 0) + 1

    top_picks = build_top_picks(
        jobs=jobs,
        skill_names=[str(item.get("name") or "") for item in skills],
        preferred_district=preferred_district,
        preferred_area=preferred_area,
        gender=worker_gender,
        selected_total_by_job=selected_total_by_job,
        selected_gender_by_job=selected_gender_by_job,
    )

    unique_jobs = {}
    for section in [skill_sections, [{"items": top_picks}], [{"items": location_jobs}], [{"items": experience_jobs}], [{"items": gender_jobs}], [{"items": jobs}]]:
        for group in section:
            for item in group.get("items", []):
                unique_jobs[str(item["id"])] = item
    attach_employer_names(list(unique_jobs.values()))
    attach_reaction_counts(list(unique_jobs.values()), user_id)

    return {
        "preferred_area": preferred_area or None,
        "preferred_city": preferred_district or None,
        "filters": {"city": selected_city or None, "area": selected_area or None,
                    "skill": requested_skill or None, "search": search_term or None, "sort_by": sort_by},
        "experience_level": experience,
        "experience_label": experience_labels.get(experience, experience.replace("_", " ").title()),
        "gender": worker_gender,
        "skills": skills,
        "top_picks": {
            "count": len(top_picks),
            "matching": {
                "district": preferred_district or None,
                "area": preferred_area or None,
                "gender": worker_gender,
                "skill_titles": [str(item.get("name") or "") for item in skills],
            },
        },
        "sections": {
            "top_picks": top_picks,
            "skills": skill_sections,
            "location": location_jobs[:20],
            "experience": experience_jobs[:20],
            "gender": gender_jobs[:20],
            "all_jobs": jobs[:30],
        },
    }
