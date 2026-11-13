"""Notification helpers.

CONTACT SHARING RULE (selected workers only)
  An employer selecting a worker is the employer's explicit decision to be contacted by that worker.
  The employer's contact details are therefore attached to the worker's "application_selected"
  notification, but ONLY:
    * live, at the moment the worker reads it (nothing private is stored in the notifications table), and
    * while that application is still "selected" and belongs to the reading worker.
  If the worker withdraws or the employer changes the decision, the details disappear immediately.
"""
import logging

from app.auth.db import admin_db

logger = logging.getLogger(__name__)

SELECTED_TYPE = "application_selected"
UNAVAILABLE_NOTE = "These contact details are no longer available because this application is no longer selected."


def _email(user_id: str) -> str | None:
    try:
        return admin_db.auth.admin.get_user_by_id(user_id).user.email
    except Exception:
        logger.exception("Could not load email for %s", user_id)
        return None


def _contact_for_employer(employer_id: str) -> dict:
    profile = admin_db.table("profiles").select("phone").eq("id", employer_id).limit(1).execute().data or [{}]
    employer = (
        admin_db.table("employer_profiles").select("organisation_name, contact_person").eq("user_id", employer_id).limit(1).execute()
    ).data or [{}]
    return {
        "organisation_name": employer[0].get("organisation_name"),
        "contact_person": employer[0].get("contact_person"),
        "phone": profile[0].get("phone"),
        "email": _email(employer_id),
    }


def attach_contacts(items: list[dict], worker_id: str) -> list[dict]:
    """Add `contact_available` / `contact` to application_selected notifications. Other types are untouched."""
    selected = [i for i in items if i.get("type") == SELECTED_TYPE]
    if not selected:
        return items

    app_ids = [str((i.get("data") or {}).get("application_id")) for i in selected if (i.get("data") or {}).get("application_id")]
    apps = {}
    if app_ids:
        rows = admin_db.table("applications").select("id, job_id, worker_id, status").in_("id", app_ids).execute().data or []
        apps = {r["id"]: r for r in rows}
    jobs = {}
    job_ids = list({a["job_id"] for a in apps.values()})
    if job_ids:
        jobs = {j["id"]: j["employer_id"] for j in admin_db.table("jobs").select("id, employer_id").in_("id", job_ids).execute().data or []}

    cache: dict[str, dict] = {}
    for item in selected:
        app = apps.get(str((item.get("data") or {}).get("application_id")))
        still_selected = bool(app and app["worker_id"] == worker_id and app["status"] == "selected")
        employer_id = jobs.get(app["job_id"]) if still_selected else None
        if still_selected and employer_id:
            if employer_id not in cache:
                cache[employer_id] = _contact_for_employer(employer_id)
            item["contact_available"], item["contact"] = True, cache[employer_id]
        else:
            item["contact_available"], item["contact"], item["contact_note"] = False, None, UNAVAILABLE_NOTE
    return items