# AbiHub profile, location and session update

## Required production migration

The deployed server log showed PostgreSQL error `42703`: `worker_profiles.preferred_state` does not exist.
This means the SQL migration has not been run in the Supabase database used by the deployed backend.

Run in the Supabase SQL Editor for the project configured in Render:
1. `003_job_location_dropdowns.sql` if location tables are not already present.
2. `004_worker_preferred_location.sql` (required).

Verify both `preferred_state` and `preferred_district` exist in `public.worker_profiles` before retesting the app.
See `API_MODULE_CONNECTION_MAP.md` for the verification SQL and complete route-to-screen map.

## Profile API

Worker profile reads and updates now return an actionable 503 message if the new location columns are missing,
instead of a generic server error. Experience-level values are validated against the database values:
`fresher`, `less_than_1_year`, `1_to_3_years`, `3_to_5_years`, and `5_plus_years`.
The Flutter app shows friendly labels but submits those exact values.

`PUT /profile/skills` accepts an empty `skill_ids` array so a worker can remove all selected skills.

## Session refresh

`POST /auth/refresh` distinguishes an explicitly invalid/expired refresh token from a temporary provider outage.
Invalid tokens return 401; temporary failures return 503 so the mobile app retains the saved session and offers retry.
