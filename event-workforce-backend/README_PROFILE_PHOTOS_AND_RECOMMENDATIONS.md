# AbiHub profile photos and worker recommendations

## Database setup
Run `005_profile_photos.sql` in the Supabase SQL Editor for the same project configured in the backend `.env`.
This adds `profiles.avatar_url` and creates the public `profile-photos` Storage bucket. Only profile photos belong in this bucket; keep employer verification documents private.

## Backend
- `POST /profile/avatar` accepts multipart form-data field `file` (JPG/PNG/WEBP, max 3 MB).
- `GET /profile/me` now includes `profile.avatar_url` and, for workers, selected `skills` with IDs and names.
- `GET /recommendations/jobs` returns open future jobs ranked by preferred area, district and state. It requires a worker bearer token.

## Flutter
Run `flutter pub get` after extracting the updated Flutter project. Add/change profile photo from Profile > Edit profile. The home banner opens job discovery; the Applications quick-access card selects the Applications tab. Selected skill chips use green check icons.
