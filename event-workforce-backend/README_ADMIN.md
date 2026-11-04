# Admin Module

All routes are prefixed with `/admin` and require:
- a valid Supabase access token,
- `profiles.role = 'admin'`,
- an active matching row in `admin_access`.

## Routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/admin/me` | Confirm current admin access |
| GET | `/admin/dashboard/stats` | Dashboard counts |
| GET | `/admin/employer-verifications?status=pending&limit=25&offset=0` | Paginated verification queue |
| GET | `/admin/employer-verifications/{submission_id}` | Submission, employer profile, and documents |
| GET | `/admin/documents/{document_id}/signed-url` | Private document link (expires in 60 seconds) |
| PATCH | `/admin/documents/{document_id}` | Approve/reject one document |
| PATCH | `/admin/employer-verifications/{submission_id}` | Approve/reject/request more information |
| GET | `/admin/audit-log?limit=50&offset=0` | Paginated admin activity history |

## Approval rule

An employer submission can only be approved after at least one supporting document exists and every document on that submission has `review_status = 'approved'`. The employer's `employer_profiles.verification_status` is updated with the decision. The app should show the blue tick only when this status is `approved` (or the verification API returns `verified: true`).

## Single admin

The database unique partial index `idx_only_one_active_admin` on `admin_access(is_active) WHERE is_active = true` enforces one active admin. Do not add a public admin registration endpoint.

Provision the first admin out-of-band:
```powershell
$env:ADMIN_USER_ID = "<existing-user-uuid>"
python -m scripts.bootstrap_admin
```

To replace the admin, deactivate the current row using the Supabase SQL editor (after confirming the replacement process):
```sql
UPDATE public.admin_access
SET is_active = false, deactivated_at = now()
WHERE is_active = true;
```
Then run the bootstrap script for the replacement existing account. Do not delete audit-log rows.
