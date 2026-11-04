# Employer Verification and Admin API

## Added routes

### Employer verification
- `POST /employer-verification/submit`
- `GET /employer-verification/me`
- `POST /employer-verification/documents?document_type=business_registration` (multipart form field: `file`)
- `GET /employer-verification/documents`

Uploads are restricted to PDF/JPEG, checked by MIME type and file signature,
and capped at 5 MiB. Files are stored in the private
`employer-verification-documents` bucket. The service-role key remains backend-only.

### Admin
- `GET /admin/me`
- `GET /admin/dashboard/stats`
- `GET /admin/employer-verifications`
- `GET /admin/employer-verifications/{submission_id}`
- `GET /admin/documents/{document_id}/signed-url`
- `PATCH /admin/employer-verifications/{submission_id}`
- `PATCH /admin/documents/{document_id}`

Admin review decisions: `approved`, `rejected`, `needs_more_information`.
Document decisions: `approved`, `rejected`.

## First admin provisioning

There is deliberately no public admin-registration endpoint. Create an ordinary
Supabase Auth user first, then set `ADMIN_USER_ID` to that user's UUID and run:

`python -m scripts.bootstrap_admin`

The script requires `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, refuses to run
while an active admin exists, and uses the unique active-admin index as a
database-level guard. To replace an admin, deactivate the old row in
`admin_access` and set `deactivated_at`, then run the script for the replacement.
Retain the old profile/audit history; do not delete audit records.

## Dependencies and configuration

Install `python-multipart` if it is not already installed, because the upload
endpoint accepts multipart form uploads:

`pip install python-multipart`

Existing `.env` must contain `SUPABASE_URL`, `SUPABASE_KEY`, and
`SUPABASE_SERVICE_KEY`. Never commit or distribute `.env`.

## Important integration notes

- These APIs use the existing `employer_profiles.verification_status` field.
- Employer profile must exist before verification submission.
- An employer must submit a verification request before uploading documents.
- Dashboard counts use exact PostgREST counts and may need pagination/filters later.
- Storage uploads/downloads are mediated by FastAPI; no client Storage policies
  are required for this backend-mediated design.
- The database schema supplied for the new tables did not include FK/index/check
  definitions. The API assumes the listed column names and the existing unique
  partial index on `admin_access(is_active) WHERE is_active = true`.
