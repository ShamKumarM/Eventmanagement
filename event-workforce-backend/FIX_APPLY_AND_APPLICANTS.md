# Fix: worker apply + employer review applicants

## Root cause
`app/applications/router.py` had the application-accepted notification block accidentally inserted inside `_get_job()`. That helper is called by:
- `POST /applications` (worker applies)
- `GET /jobs/{job_id}/applications` (employer reviews applicants)
- Other application operations that load the job

The misplaced block referenced `new`, `current`, `app`, and `application_id`, none of which exist in `_get_job()`. Both affected endpoints therefore raised a server-side NameError and Flutter displayed its generic server-unavailable message.

## Fix
Removed the misplaced block from `_get_job()`. The notification block remains in `update_application_status()` and still creates an `application_accepted` notification when an employer selects a worker.

## Validation
- Python `compileall`: passed
- Existing backend tests: 5 passed

## Deploy
Deploy this backend package to the same API host configured in Flutter. No Flutter UI change is required for this server-side regression.
