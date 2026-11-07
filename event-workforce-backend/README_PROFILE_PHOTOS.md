# AbiHub profile photos (workers and employers)

1. Run `005_profile_photos.sql` if the profile photo bucket/column has never been created.
2. Run `006_profile_photo_format_support.sql` after it. This updates the public bucket to accept the normalized JPEG output and raises the upload limit to 15 MB.
3. Install backend dependencies with `pip install -r requirements.txt`.
4. Restart FastAPI.
5. Authenticated endpoint: `POST /profile/avatar`, multipart form field `file`.
6. The API decodes supported image formats with Pillow, applies EXIF orientation, converts the result to JPEG, and stores one avatar per user. The Flutter app offers a circular 1:1 crop step before upload.
7. `GET /profile/me` returns `profile.avatar_url`.

The endpoint is shared by workers and employers. The profile photo bucket is public because profile pictures are intended to be visible to other app users. Keep identity, tax, and employer-verification documents in private buckets.
