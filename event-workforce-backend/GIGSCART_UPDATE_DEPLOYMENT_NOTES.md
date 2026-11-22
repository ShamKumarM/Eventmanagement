# Gigscart update – deployment notes

## Backend
- Deploy the updated FastAPI source.
- Existing application statuses remain compatible. New employer actions now transition directly from `pending` to `selected` (Accepted) or `rejected`; the old `shortlisted` value is only handled for records created by older app versions.
- Job expiry is evaluated against the scheduled end time in `Asia/Kolkata`. Worker application lists, worker job feeds, and employer current/history lists no longer depend only on the daily cleanup cron.

## Supabase SQL
Run `018_optional_job_start_time.sql` in the Supabase SQL editor after the earlier migrations. It makes `jobs.start_time` nullable while keeping `jobs.reporting_time` required. No table reset or data deletion is required.

## Flutter
- Replace the existing Flutter project with the updated source.
- Build with your current API URL:
  `flutter build apk --release --dart-define=API_BASE_URL=https://eventmanagement-s6yu.onrender.com`

## Verification
- Backend Python compilation completed.
- Backend tests: 18 passed.
- Flutter SDK is not installed in this build environment, so run `flutter analyze` and the APK build locally before release.
