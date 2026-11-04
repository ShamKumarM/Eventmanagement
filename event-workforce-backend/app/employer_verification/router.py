
"""Employer verification submission and private document management."""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field

from app.auth.deps import get_current_user
from app.auth.db import admin_db


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/employer-verification",
    tags=["Employer Verification"],
)

BUCKET = "employer-verification-documents"
MAX_FILE_BYTES = 5 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
}

ALLOWED_DOCUMENT_TYPES = {
    "business_registration",
    "gst_certificate",
    "business_license",
    "address_proof",
    "other",
}


class VerificationSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_information_accurate: bool = Field(
        description="Must be true to submit the verification request."
    )


def _employer(user):
    result = (
        admin_db.table("profiles")
        .select("id, role, role_selected")
        .eq("id", str(user.id))
        .limit(1)
        .execute()
    )

    if (
        not result.data
        or result.data[0].get("role") != "employer"
        or not result.data[0].get("role_selected")
    ):
        raise HTTPException(
            status_code=403,
            detail="This feature is available only to selected employer accounts.",
        )

    profile = (
        admin_db.table("employer_profiles")
        .select("user_id, organisation_name, verification_status")
        .eq("user_id", str(user.id))
        .limit(1)
        .execute()
    )

    if not profile.data:
        raise HTTPException(
            status_code=404,
            detail="Employer profile not found. Complete your employer profile first.",
        )

    return profile.data[0]


def _latest_submission(user_id: str):
    result = (
        admin_db.table("employer_verification_submissions")
        .select("*")
        .eq("employer_user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


@router.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_verification(
    payload: VerificationSubmit,
    user=Depends(get_current_user),
):
    _employer(user)

    if not payload.confirm_information_accurate:
        raise HTTPException(
            status_code=422,
            detail="Confirm that the submitted information is accurate.",
        )

    latest = _latest_submission(str(user.id))

    if latest and latest.get("status") in {
        "pending",
        "needs_more_information",
    }:
        raise HTTPException(
            status_code=409,
            detail="You already have a verification submission awaiting review.",
        )

    try:
        created = (
            admin_db.table("employer_verification_submissions")
            .insert({
                "employer_user_id": str(user.id),
                "status": "pending",
            })
            .execute()
        )

        if not created.data:
            raise RuntimeError("Submission insert returned no row.")

        submission = created.data[0]

        admin_db.table("employer_profiles").update(
            {"verification_status": "pending"}
        ).eq("user_id", str(user.id)).execute()

        return {
            "message": "Verification submitted. Upload your supporting documents.",
            "submission": submission,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Employer verification submission failed. Employer ID: %s",
            user.id,
        )

        raise HTTPException(
            status_code=503,
            detail="Could not submit verification. Please try again.",
        )


@router.get("/me")
def get_my_verification(user=Depends(get_current_user)):
    employer = _employer(user)

    submission = _latest_submission(str(user.id))

    docs_result = (
        admin_db.table("employer_verification_documents")
        .select(
            "id, submission_id, document_type, original_filename, "
            "mime_type, size_bytes, review_status, created_at, "
            "reviewed_at, review_note"
        )
        .eq("employer_user_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "verification_status": (
            submission.get("status")
            if submission
            else employer.get("verification_status", "not_started")
        ),
        "submission": submission,
        "documents": docs_result.data or [],
        "verified": bool(
            submission and submission.get("status") == "approved"
        ),
    }


@router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    document_type: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    _employer(user)

    # Validate document category.
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                "document_type must be one of: "
                + ", ".join(sorted(ALLOWED_DOCUMENT_TYPES))
            ),
        )

    # Ensure the employer has an active submission.
    submission = _latest_submission(str(user.id))

    if not submission or submission.get("status") not in {
        "pending",
        "needs_more_information",
    }:
        raise HTTPException(
            status_code=409,
            detail="Submit a verification request before uploading documents.",
        )

    # Validate MIME type.
    mime_type = (file.content_type or "").lower()

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only PDF and JPEG documents are accepted.",
        )

    object_path = None
    uploaded_to_storage = False

    try:
        # Read maximum allowed size + 1 byte to detect oversized files.
        content = await file.read(MAX_FILE_BYTES + 1)

        if not content:
            raise HTTPException(
                status_code=422,
                detail="The uploaded file is empty.",
            )

        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Each document must be 5 MiB or smaller.",
            )

        # Validate actual file signature.
        if mime_type == "application/pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=415,
                    detail="The file content does not appear to be a valid PDF.",
                )

        elif mime_type == "image/jpeg":
            if not content.startswith(b"\xff\xd8\xff"):
                raise HTTPException(
                    status_code=415,
                    detail="The file content does not appear to be a valid JPEG.",
                )

        # Generate a unique private storage path.
        suffix = ALLOWED_MIME_TYPES[mime_type]

        safe_name = Path(
            file.filename or f"document{suffix}"
        ).name[:180]

        object_path = (
            f"{user.id}/{submission['id']}/{uuid4().hex}{suffix}"
        )

        # STEP 1: Upload file to private Supabase Storage.
        try:
            storage_result = (
                admin_db.storage
                .from_(BUCKET)
                .upload(
                    object_path,
                    content,
                    file_options={
                        "content-type": mime_type,
                        "upsert": "false",
                    },
                )
            )

            uploaded_to_storage = True

            logger.info(
                "Verification document uploaded to storage. "
                "Employer ID: %s, Path: %s",
                user.id,
                object_path,
            )

        except Exception:
            logger.exception(
                "SUPABASE STORAGE UPLOAD FAILED. "
                "Employer ID: %s, Bucket: %s, Path: %s",
                user.id,
                BUCKET,
                object_path,
            )

            raise HTTPException(
                status_code=503,
                detail="Could not upload the document to storage. Please try again.",
            )

        # STEP 2: Save document metadata in PostgreSQL.
        try:
            inserted = (
                admin_db.table("employer_verification_documents")
                .insert({
                    "submission_id": submission["id"],
                    "employer_user_id": str(user.id),
                    "document_type": document_type,
                    "original_filename": safe_name,
                    "storage_path": object_path,
                    "mime_type": mime_type,
                    "size_bytes": len(content),
                    "review_status": "pending",
                })
                .execute()
            )

            if not inserted.data:
                raise RuntimeError(
                    "Document metadata insert returned no row."
                )

        except Exception:
            logger.exception(
                "DOCUMENT METADATA INSERT FAILED. "
                "Employer ID: %s, Path: %s",
                user.id,
                object_path,
            )

            raise HTTPException(
                status_code=503,
                detail="File uploaded, but its document record could not be saved.",
            )

        # STEP 3: Return successful response.
        logger.info(
            "Employer verification document saved successfully. "
            "Employer ID: %s, Document ID: %s",
            user.id,
            inserted.data[0]["id"],
        )

        return {
            "message": "Document uploaded successfully.",
            "document": inserted.data[0],
        }

    except HTTPException:
        # If metadata saving failed after upload, remove orphaned file.
        if uploaded_to_storage and object_path:
            try:
                (
                    admin_db.storage
                    .from_(BUCKET)
                    .remove([object_path])
                )

                logger.info(
                    "Cleaned up uploaded file after failure: %s",
                    object_path,
                )

            except Exception:
                logger.exception(
                    "FAILED TO CLEAN UP STORAGE FILE: %s",
                    object_path,
                )

        raise

    except Exception:
        logger.exception(
            "UNEXPECTED DOCUMENT UPLOAD ERROR. Employer ID: %s",
            user.id,
        )

        if uploaded_to_storage and object_path:
            try:
                (
                    admin_db.storage
                    .from_(BUCKET)
                    .remove([object_path])
                )
            except Exception:
                logger.exception(
                    "FAILED TO CLEAN UP STORAGE FILE: %s",
                    object_path,
                )

        raise HTTPException(
            status_code=503,
            detail="Could not save the document. Please try again.",
        )

    finally:
        await file.close()


@router.get("/documents")
def list_my_documents(user=Depends(get_current_user)):
    _employer(user)

    result = (
        admin_db.table("employer_verification_documents")
        .select(
            "id, submission_id, document_type, original_filename, "
            "mime_type, size_bytes, review_status, created_at, "
            "reviewed_at, review_note"
        )
        .eq("employer_user_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []
