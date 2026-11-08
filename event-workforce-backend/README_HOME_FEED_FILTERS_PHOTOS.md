# AbiHub home feed, filters and profile-photo update

## Changes
- `GET /recommendations/home` now accepts `city`, `area`, repeated `skill_id` values and `sort_by=recent|salary`.
- The recommendation response includes all active skills so the filter can offer skills beyond the worker's currently selected skills.
- `GET /profile/me` includes `profile.avatar_url`.
- `POST /profile/avatar` accepts uploaded images, validates/decodes them with Pillow, center-crops to a square 512x512 JPEG, uploads to the private/public-facing `profile-photos` bucket configured by the migration, and saves the URL.
- `GET /jobs` accepts `sort_by=recent|earliest|salary`, and city/area matching is partial text matching.

## Required Supabase setup
Run these SQL files in order in the same Supabase project used by this backend:
1. `005_profile_photos.sql`
2. `006_profile_photo_format_support.sql`

The API normalizes accepted source formats to JPEG. Install dependencies from `requirements.txt` (Pillow is included). Keep the service-role key on the backend only.

## Filter examples
- `/recommendations/home?city=Coimbatore&area=Kalapatti&sort_by=recent`
- `/recommendations/home?skill_id=1&skill_id=8&sort_by=salary`
- `/jobs?city=Coimbatore&area=Kalapatti&sort_by=recent&page=1&page_size=30`

`nearest` sorting is intentionally not exposed until a trusted user-origin coordinate is available; the UI does not pretend a text-area match is distance sorting.
