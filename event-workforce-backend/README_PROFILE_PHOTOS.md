# AbiHub profile photos

1. Run `005_profile_photos.sql` in the Supabase SQL Editor for the same project configured in the backend `.env`.
2. Restart the FastAPI backend.
3. Authenticated endpoint: `POST /profile/avatar` using `multipart/form-data` with field name `file`.
4. Accepted formats: JPG, PNG, WEBP. Maximum size: 5 MB.
5. `GET /profile/me` returns `profile.avatar_url`.

The `profile-photos` bucket is public because profile pictures are intended to be visible to other app users. Keep identity, tax, and employer-verification documents in private buckets.
