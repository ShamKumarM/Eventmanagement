# AbiHub module and API connection map

This file documents the API routes in this backend and the Flutter screens that call them.
The admin verification-management interface is intended to be a separate web app; the mobile app
shows the admin dashboard and queue overview only.

## Authentication (`/auth`)
| Method | Route | Purpose | Flutter usage |
|---|---|---|---|
| POST | `/auth/register` | Create account | Register screen |
| POST | `/auth/login` | Sign in and receive tokens | Login screen |
| GET | `/auth/me` | Current user and selected role | Session gate and dashboard |
| POST | `/auth/select-role` | Select worker/employer role | Role selection screen |
| POST | `/auth/refresh` | Rotate access and refresh tokens | API interceptor/session restore |
| POST | `/auth/logout` | Validate logout request | Explicit sign-out; client clears tokens |
| POST | `/auth/forgot-password` | Send password recovery email | Forgot-password screen |
| GET | `/auth/recovery/callback` | Browser recovery page | Email recovery link |
| POST | `/auth/reset-password` | Save new password | Recovery page |

## Jobs (`/`)
| Method | Route | Purpose | Flutter usage |
|---|---|---|---|
| GET | `/categories` | Active job categories | Create-job form |
| GET | `/locations/states` | State dropdown | Create-job and worker profile forms |
| GET | `/locations/districts?state_id=...` | District dropdown | Create-job and worker profile forms |
| GET | `/locations/areas?district_id=...` | Locality dropdown | Create-job and worker profile forms |
| POST | `/jobs` | Publish job | Employer create-job form |
| GET | `/jobs/mine` | Employer's jobs | Employer My Jobs tab |
| PATCH | `/jobs/{job_id}` | Edit own job | API available; editor UI can be added |
| POST | `/jobs/{job_id}/cancel` | Cancel own job | API available; management UI can be added |
| GET | `/jobs` | Open job feed | Worker Explore Jobs tab |
| GET | `/jobs/{job_id}` | Job detail | Worker job detail |

Job creation requires state, district, area, venue name and full address. It does **not** require latitude or longitude.
Optional `lat`, `lng` and `radius_km` query parameters remain only for distance-based job-feed filtering.

## Profile (`/profile`)
| Method | Route | Purpose | Flutter usage |
|---|---|---|---|
| GET | `/profile/me` | Shared + role-specific profile | Profile view and edit form |
| PATCH | `/profile/me` | Update name and phone | Profile edit form |
| GET | `/profile/completion` | Worker completion score | Worker home |
| GET | `/profile/skills` | Available worker skills | Worker profile edit |
| GET | `/profile/worker` | Worker profile details | API available |
| PATCH | `/profile/worker` | Save worker preferences | Worker profile edit |
| PUT | `/profile/skills` | Replace worker skills | Worker profile edit |
| GET | `/profile/employer` | Employer business details | API available |
| PATCH | `/profile/employer` | Save employer business details | Employer profile edit |

Experience-level values sent to the API must be the database enum values:
`fresher`, `less_than_1_year`, `1_to_3_years`, `3_to_5_years`, `5_plus_years`.
The Flutter form displays human-readable labels while sending these exact values.

## Applications (`/applications`)
| Method | Route | Purpose | Flutter usage |
|---|---|---|---|
| POST | `/applications` | Apply to a job | Worker job detail |
| GET | `/applications/mine` | Current worker's applications | Worker Applications tab |
| POST | `/applications/{application_id}/withdraw` | Withdraw application | API available |
| GET | `/jobs/{job_id}/applications` | Employer applicants for a job | API available |
| PATCH | `/applications/{application_id}/status` | Employer updates application status | API available |

## Employer verification (`/employer-verification`)
| Method | Route | Purpose | Flutter usage |
|---|---|---|---|
| POST | `/submit` | Submit or resume verification request | Employer Verification centre |
| GET | `/me` | Current status, submission and documents | Employer Verification centre |
| POST | `/documents` | Upload private PDF/JPEG document | Verification Documents screen |
| GET | `/documents` | List employer's own documents | Verification Documents screen |

The employer submit operation is idempotent for an already-pending request. Repeated taps do not create duplicate submissions.
Document uploads require a pending or needs-more-information submission.

## Admin (`/admin`)
| Method | Route | Purpose | Flutter usage |
|---|---|---|---|
| GET | `/me` | Verify active administrator access | API available |
| GET | `/dashboard/stats` | Dashboard counters | Admin dashboard |
| GET | `/employer-verifications` | Verification queue | Admin queue tab |
| GET | `/employer-verifications/{submission_id}` | Submission and document details | Separate admin web app |
| GET | `/documents/{document_id}/signed-url` | Short-lived private document URL | Separate admin web app |
| PATCH | `/documents/{document_id}` | Approve/reject a document | Separate admin web app |
| PATCH | `/employer-verifications/{submission_id}` | Approve/reject/request more info | Separate admin web app |
| GET | `/audit-log` | Admin action history | Admin audit tab |

Admin audit actions are mapped to the database CHECK constraint values:
`verification_approved`, `verification_rejected`,
`verification_more_information_requested`, `verification_document_accepted`,
`verification_document_rejected`, `verification_suspended`,
`admin_activated`, `admin_deactivated`.

## Production database migration — REQUIRED

The supplied Render log proves the deployed Supabase database is missing
`worker_profiles.preferred_state` (PostgreSQL error `42703`). Deploying the Python code alone
does not apply SQL migrations.

Run these files in the **Supabase project whose URL is configured in the Render service**:

1. `003_job_location_dropdowns.sql` (only if the location tables/job columns are not already installed).
2. `004_worker_preferred_location.sql` (required for the new worker location dropdowns).

Then verify in Supabase SQL Editor:

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'worker_profiles'
  and column_name in ('preferred_state', 'preferred_district')
order by column_name;
```

Expected result: two rows, `preferred_district` and `preferred_state`.

Also verify the location tables contain active options:

```sql
select s.name as state, d.name as district, a.name as area
from public.location_states s
join public.location_districts d on d.state_id = s.id
join public.location_areas a on a.district_id = d.id
where s.is_active and d.is_active and a.is_active
order by s.name, d.name, a.name
limit 30;
```

After running the migration, restart/redeploy the backend and test:
`GET /profile/me`, `GET /profile/completion`, and all three location dropdown endpoints.
Do not paste service-role keys or `.env` values into chat or commit them to Git.
