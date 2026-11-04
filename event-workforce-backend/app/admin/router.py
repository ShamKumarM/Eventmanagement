"""Admin APIs for dashboard metrics and employer verification review.

All endpoints require both an active admin_access row and profiles.role='admin'.
The service-role Supabase client is used only inside this trusted backend module.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.deps import get_current_user
from app.auth.db import admin_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

VERIFICATION_STATUSES = {
    "pending", "approved", "rejected", "needs_more_information"
}


def require_admin(user=Depends(get_current_user)):
    """Require a valid Supabase user, admin role, and the sole active admin grant."""
    user_id = str(user.id)
    try:
        access = (
            admin_db.table("admin_access")
            .select("user_id, is_active")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        profile = (
            admin_db.table("profiles")
            .select("id, role")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.exception("Admin authorization lookup failed for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify administrator access.",
        ) from exc

    if (
        not access.data
        or not profile.data
        or profile.data[0].get("role") != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active administrator access is required.",
        )
    return user


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(
        pattern="^(approved|rejected|needs_more_information)$"
    )
    notes: str | None = Field(default=None, max_length=2000)


class DocumentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=1000)


def _audit(
    actor_id: str,
    action: str,
    employer_id: str | None = None,
    submission_id: str | None = None,
    document_id: str | None = None,
    details: dict | None = None,
):
    admin_db.table("admin_audit_log").insert({
        "actor_admin_id": actor_id,
        "action": action,
        "employer_user_id": employer_id,
        "submission_id": submission_id,
        "document_id": document_id,
        "details": details or {},
    }).execute()


def _count(table: str, filters: dict | None = None) -> int:
    query = admin_db.table(table).select("*", count="exact", head=True)
    for column, value in (filters or {}).items():
        query = query.eq(column, value)
    return query.execute().count or 0


def _attach_employer_profiles(rows: list[dict]) -> list[dict]:
    """Embed employer profile data without relying on an ambiguous FK relationship."""
    user_ids = list({row["employer_user_id"] for row in rows if row.get("employer_user_id")})
    if not user_ids:
        return rows
    profiles = (
        admin_db.table("employer_profiles")
        .select(
            "user_id, organisation_name, description, contact_person, "
            "business_area, business_type, business_address, "
            "years_in_business, website_url, verification_status"
        )
        .in_("user_id", user_ids)
        .execute()
    )
    by_user = {row["user_id"]: row for row in (profiles.data or [])}
    for row in rows:
        row["employer_profile"] = by_user.get(row.get("employer_user_id"))
    return rows


@router.get("/me")
def admin_me(user=Depends(require_admin)):
    return {"admin_user_id": str(user.id), "active": True}


@router.get("/dashboard/stats")
def dashboard_stats(user=Depends(require_admin)):
    try:
        return {
            "total_users": _count("profiles"),
            "total_employers": _count("profiles", {"role": "employer"}),
            "total_workers": _count("profiles", {"role": "worker"}),
            "total_jobs": _count("jobs"),
            "open_jobs": _count("jobs", {"status": "open"}),
            "pending_verifications": _count(
                "employer_verification_submissions", {"status": "pending"}
            ),
            "needs_more_information": _count(
                "employer_verification_submissions",
                {"status": "needs_more_information"},
            ),
            "approved_employers": _count(
                "employer_profiles", {"verification_status": "approved"}
            ),
        }
    except Exception as exc:
        logger.exception("Admin dashboard statistics query failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load dashboard statistics.",
        ) from exc


@router.get("/employer-verifications")
def list_verifications(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_admin),
):
    if status_filter and status_filter not in VERIFICATION_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported verification status.")
    try:
        query = (
            admin_db.table("employer_verification_submissions")
            .select("*", count="exact")
            .order("submitted_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if status_filter:
            query = query.eq("status", status_filter)
        result = query.execute()
        rows = _attach_employer_profiles(result.data or [])
        return {
            "items": rows,
            "total": result.count or 0,
            "limit": limit,
            "offset": offset,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not list employer verification submissions")
        raise HTTPException(status_code=503, detail="Could not load verification submissions.") from exc


@router.get("/employer-verifications/{submission_id}")
def get_verification(submission_id: UUID, user=Depends(require_admin)):
    try:
        result = (
            admin_db.table("employer_verification_submissions")
            .select("*")
            .eq("id", str(submission_id))
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Verification submission not found.")
        submission = _attach_employer_profiles(result.data)[0]
        docs = (
            admin_db.table("employer_verification_documents")
            .select(
                "id, submission_id, employer_user_id, document_type, "
                "original_filename, mime_type, size_bytes, review_status, "
                "created_at, reviewed_at, reviewed_by, review_note"
            )
            .eq("submission_id", str(submission_id))
            .order("created_at")
            .execute()
        )
        return {"submission": submission, "documents": docs.data or []}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not load verification submission %s", submission_id)
        raise HTTPException(status_code=503, detail="Could not load verification details.") from exc


@router.get("/documents/{document_id}/signed-url")
def get_document_signed_url(document_id: UUID, user=Depends(require_admin)):
    try:
        result = (
            admin_db.table("employer_verification_documents")
            .select("id, storage_path, original_filename")
            .eq("id", str(document_id))
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found.")
        signed = admin_db.storage.from_("employer-verification-documents").create_signed_url(
            result.data[0]["storage_path"], 60
        )
        url = signed.get("signedURL") or signed.get("signedUrl")
        if not url:
            raise RuntimeError("Supabase did not return a signed URL.")
        return {
            "signed_url": url,
            "filename": result.data[0]["original_filename"],
            "expires_in_seconds": 60,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not create signed URL for document %s", document_id)
        raise HTTPException(
            status_code=503,
            detail="Could not generate a document access link.",
        ) from exc


@router.patch("/documents/{document_id}")
def review_document(
    document_id: UUID,
    payload: DocumentDecision,
    user=Depends(require_admin),
):
    try:
        result = (
            admin_db.table("employer_verification_documents")
            .select("id, employer_user_id, submission_id, review_status")
            .eq("id", str(document_id))
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found.")
        document = result.data[0]

        submission_result = (
            admin_db.table("employer_verification_submissions")
            .select("status")
            .eq("id", document["submission_id"])
            .limit(1)
            .execute()
        )
        if not submission_result.data:
            raise HTTPException(status_code=404, detail="Parent verification submission not found.")
        if submission_result.data[0]["status"] not in {"pending", "needs_more_information"}:
            raise HTTPException(status_code=409, detail="This verification has already been decided.")

        now = datetime.now(timezone.utc).isoformat()
        updated = (
            admin_db.table("employer_verification_documents")
            .update({
                "review_status": payload.decision,
                "reviewed_at": now,
                "reviewed_by": str(user.id),
                "review_note": payload.note,
            })
            .eq("id", str(document_id))
            .execute()
        )
        _audit(
            str(user.id),
            f"verification_document_{payload.decision}",
            employer_id=document["employer_user_id"],
            submission_id=document["submission_id"],
            document_id=str(document_id),
            details={"note": payload.note},
        )
        return {
            "message": "Document review saved.",
            "document": updated.data[0] if updated.data else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not review verification document %s", document_id)
        raise HTTPException(status_code=503, detail="Could not save the document review.") from exc


@router.patch("/employer-verifications/{submission_id}")
def review_verification(
    submission_id: UUID,
    payload: ReviewDecision,
    user=Depends(require_admin),
):
    try:
        result = (
            admin_db.table("employer_verification_submissions")
            .select("id, employer_user_id, status")
            .eq("id", str(submission_id))
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Verification submission not found.")
        submission = result.data[0]
        if submission["status"] not in {"pending", "needs_more_information"}:
            raise HTTPException(status_code=409, detail="This submission has already been decided.")

        if payload.decision == "approved":
            docs_result = (
                admin_db.table("employer_verification_documents")
                .select("id, review_status")
                .eq("submission_id", str(submission_id))
                .execute()
            )
            docs = docs_result.data or []
            if not docs:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot approve an employer without supporting documents.",
                )
            if any(doc.get("review_status") != "approved" for doc in docs):
                raise HTTPException(
                    status_code=409,
                    detail="Review and approve every supporting document before approving the employer.",
                )

        now = datetime.now(timezone.utc).isoformat()
        updated = (
            admin_db.table("employer_verification_submissions")
            .update({
                "status": payload.decision,
                "reviewed_at": now,
                "reviewed_by": str(user.id),
                "review_notes": payload.notes,
                "updated_at": now,
            })
            .eq("id", str(submission_id))
            .execute()
        )
        admin_db.table("employer_profiles").update({
            "verification_status": payload.decision
        }).eq("user_id", submission["employer_user_id"]).execute()

        _audit(
            str(user.id),
            f"employer_verification_{payload.decision}",
            employer_id=submission["employer_user_id"],
            submission_id=str(submission_id),
            details={"notes": payload.notes},
        )
        return {
            "message": "Verification decision saved.",
            "submission": updated.data[0] if updated.data else None,
            "verified": payload.decision == "approved",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not save verification decision for %s", submission_id)
        raise HTTPException(
            status_code=503,
            detail="Could not save the verification decision.",
        ) from exc


@router.get("/audit-log")
def list_audit_log(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_admin),
):
    try:
        result = (
            admin_db.table("admin_audit_log")
            .select("*", count="exact")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return {
            "items": result.data or [],
            "total": result.count or 0,
            "limit": limit,
            "offset": offset,
        }
    except Exception as exc:
        logger.exception("Could not load admin audit log")
        raise HTTPException(status_code=503, detail="Could not load audit history.") from exc
