# Profile Management module

This module uses the existing hosted Supabase tables:
- `profiles`
- `worker_profiles`
- `employer_profiles`
- `skills`
- `worker_profile_skills`

No new database tables or migrations are required for the profile endpoints.

## Endpoints

All endpoints except `/health` require `Authorization: Bearer <access_token>`.

| Method | Path | Access |
|---|---|---|
| GET | `/profile/me` | Any authenticated user |
| PATCH | `/profile/me` | Any authenticated user; only `full_name`, `phone` |
| GET | `/profile/completion` | Selected worker |
| GET | `/profile/skills` | Any authenticated user |
| GET | `/profile/worker` | Selected worker |
| PATCH | `/profile/worker` | Selected worker |
| PUT | `/profile/skills` | Selected worker |
| GET | `/profile/employer` | Selected employer |
| PATCH | `/profile/employer` | Selected employer |

Employer `verification_status`, account role, and `role_selected` are deliberately not writable through profile endpoints.

## Worker application eligibility

Completion is calculated from five required fields, each worth 20%:
- `profiles.full_name`
- `profiles.phone`
- `worker_profiles.preferred_area`
- at least one row in `worker_profile_skills`
- `worker_profiles.experience_level`

`GET /profile/completion` returns `application_eligible: true` only at 100%. This endpoint reports eligibility; the application module must enforce it in the apply endpoint too.

## Postman examples

Use the same `{{base_url}}` and `{{access_token}}` variables already used by the Jobs collection.

### 1. Get current profile
`GET {{base_url}}/profile/me`

Authorization: Bearer Token `{{access_token}}`

### 2. Update name and phone
`PATCH {{base_url}}/profile/me`

Body (raw JSON):
```json
{
  "full_name": "Sham Kumar",
  "phone": "+919876543210"
}
```

### 3. Update worker fields
`PATCH {{base_url}}/profile/worker`

```json
{
  "bio": "Experienced event staff member",
  "preferred_area": "Gandhipuram",
  "preferred_radius_km": 20,
  "is_available": true,
  "experience_level": "1-2 years"
}
```

`experience_level` is free text in the current database; use values such as `Beginner`, `Less than 1 year`, `1-2 years`, `3-5 years`, or `5+ years` consistently across the app.

### 4. List available skills
`GET {{base_url}}/profile/skills`

### 5. Set worker skills
`PUT {{base_url}}/profile/skills`

```json
{
  "skill_ids": [1, 2, 10]
}
```

This replaces the worker's selected skills with the supplied list. At least one skill is required by this endpoint.

### 6. Check completion
`GET {{base_url}}/profile/completion`

### 7. Get employer profile
`GET {{base_url}}/profile/employer`

### 8. Update employer business details
`PATCH {{base_url}}/profile/employer`

```json
{
  "organisation_name": "Test Events Coimbatore",
  "description": "Event staffing and coordination",
  "contact_person": "Sham Kumar",
  "business_area": "Coimbatore",
  "business_type": "Event management",
  "business_address": "Coimbatore, Tamil Nadu",
  "years_in_business": 2,
  "website_url": "https://example.com"
}
```

Do not send `verification_status`; it is intentionally excluded.

## Run locally

From the backend project root, with the existing virtual environment activated:

```bash
uvicorn app.main:app --reload
```

Use Postman, not Swagger, for testing.

## Important implementation notes

- Requests authenticate through the existing `get_current_user` dependency.
- Database reads/writes use the existing backend-only `admin_db` service-role client. Never expose `SUPABASE_SERVICE_KEY` to Postman, a browser, or a frontend.
- Profile writes are restricted by API allowlists and role checks. The service-role client bypasses RLS, so this backend must remain trusted and must never accept a caller-supplied `user_id`.
- Skills are reconciled using insert/delete operations. If a request fails mid-operation, reload the skill list and retry.
- This module does not change the job-application endpoint. Ram's application module should call or replicate the same completion rule on the server before accepting an application.
