# AbiHub profile, location and session update

## Database migration

Run these SQL files in Supabase SQL Editor in this order:

1. `003_job_location_dropdowns.sql` (if it has not already been run)
2. `004_worker_preferred_location.sql`

Migration 004 adds `preferred_state` and `preferred_district` to `worker_profiles`, seeds the legacy Coimbatore-wide locality option, and backfills existing Coimbatore preferences so existing accounts can reopen the new dropdowns without losing their saved area.

## Updated worker profile API

`GET /profile/me` and `GET /profile/worker` now include:

- `preferred_state`
- `preferred_district`
- `preferred_area`

`PATCH /profile/worker` validates the state → district → area relationship when all three are submitted. The mobile app sends all three values together.

`PUT /profile/skills` accepts an empty `skill_ids` array so a worker can remove all selected skills. Non-empty values are still checked against the `skills` table.

## Session refresh

`POST /auth/refresh` now distinguishes an explicitly invalid/expired refresh token from a temporary Supabase/provider outage. Invalid tokens return 401; temporary failures return 503 so the mobile app can retain the saved session and offer retry rather than forcing sign-in.
