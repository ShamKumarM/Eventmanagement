"""Strict matching rules for the worker home Top Picks section."""

from __future__ import annotations


def _key(value: object) -> str:
    """Case/whitespace-insensitive exact comparison; deliberately not substring matching."""
    return " ".join(str(value or "").casefold().split())


def build_top_picks(
    jobs: list[dict],
    skill_names: list[str],
    preferred_district: str | None,
    preferred_area: str | None,
    gender: str | None,
    selected_total_by_job: dict[str, int] | None = None,
    selected_gender_by_job: dict[str, dict[str, int]] | None = None,
) -> list[dict]:
    """Match exact district + area + job-title skill + gender capacity.

    Legacy jobs with all gender quotas NULL remain open to every gender, but
    still need an unfilled overall position. Allocated jobs require an
    unfilled position in the worker's own gender allocation.
    """
    district_key, area_key = _key(preferred_district), _key(preferred_area)
    gender_key = _key(gender)
    skills = {_key(name) for name in skill_names if _key(name)}
    if not district_key or not area_key or not skills or gender_key not in {"male", "female", "trans"}:
        return []

    selected_total_by_job = selected_total_by_job or {}
    selected_gender_by_job = selected_gender_by_job or {}
    quota_field = {
        "male": "male_required",
        "female": "female_required",
        "trans": "trans_required",
    }[gender_key]
    result: list[dict] = []
    for job in jobs:
        if _key(job.get("district")) != district_key:
            continue
        if _key(job.get("area")) != area_key:
            continue
        if _key(job.get("title")) not in skills:
            continue

        selected_total = int(selected_total_by_job.get(str(job.get("id")), 0))
        total_required = int(job.get("workers_required") or 0)
        if total_required and selected_total >= total_required:
            continue

        quotas = (job.get("male_required"), job.get("female_required"), job.get("trans_required"))
        if all(value is None for value in quotas):
            # Backward compatibility: pre-allocation jobs are open to all genders.
            result.append(job)
            continue

        allocated = int(job.get(quota_field) or 0)
        selected_for_gender = int(
            (selected_gender_by_job.get(str(job.get("id"))) or {}).get(gender_key, 0)
        )
        if allocated > selected_for_gender:
            result.append(job)
    return result
