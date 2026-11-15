# Gigscart Top Picks update

## Worker home
- Renamed the first recommendation row to **Top Picks**.
- The Flutter app now renders only the backend `sections.top_picks` result; it no longer builds a broad recommendation list from nearby, experience, and all-jobs sections.
- When no jobs satisfy all matching rules, the screen explains why Top Picks is empty.

## Backend matching rules
A job appears in Top Picks only when:
1. `jobs.district` exactly matches `worker_profiles.preferred_district`.
2. `jobs.area` exactly matches `worker_profiles.preferred_area`.
3. `jobs.title` exactly matches one of the worker's selected `skills.name` values.
4. The worker's gender has an unfilled allocation.

Matching is case-insensitive and collapses repeated/leading/trailing spaces. It is not substring matching.

For allocated jobs, remaining gender capacity is calculated as the gender allocation minus applications with status `selected` for workers of that gender. Jobs with all three gender allocations NULL are legacy open-to-all jobs and are included only while overall worker capacity remains.

The response adds:
- `top_picks.count`
- `top_picks.matching`
- `sections.top_picks`

## Notifications icon
The worker home notification control now uses a distinctive active-notification icon in a light-blue rounded surface, with the orange unread indicator. Existing navigation and unread-refresh behavior are retained.

## Database
No new database columns or migration are required for this update. The existing `profiles.gender`, `worker_profiles.preferred_district`, `worker_profiles.preferred_area`, `worker_profile_skills`, and `jobs` gender allocation columns are reused.

If gender allocation migration `017_gender_job_allocations.sql` has not yet been applied to Supabase, run that existing migration before deploying this version.

## Verification
- Backend Python compilation: passed.
- Full backend test suite: 14 passed.
- Flutter SDK is not available in the build environment, so run `flutter analyze` and a release APK build locally after extracting the archive.
