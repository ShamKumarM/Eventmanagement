# Profile Management module

This module uses the existing hosted Supabase tables:
- `profiles`
- `worker_profiles`
- `employer_profiles`
- `skills`
- `worker_profile_skills`

The profile routes depend on migrations `003` and `004` for location lookups and
worker preferences, and `005` plus `006` for profile photos. Apply the required
files to the Supabase project used by the API before using those features.

## Endpoints

All endpoints except `/health` require `Authorization: Bearer <access_token>`.

| Method | Path | Access |
|---|---|---|
| GET | `/profile/me` | Any authenticated user |
| PATCH | `/profile/me` | Any authenticated user; only `full_name`, `phone` |
| POST | `/profile/avatar` | Any authenticated user; normalized public JPEG avatar upload |
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
  "preferred_state": "Tamil Nadu",
  "preferred_district": "Coimbatore",
  "preferred_area": "Gandhipuram",
  "preferred_radius_km": 20,
  "is_available": true,
  "experience_level": "1_to_3_years"
}
```

`experience_level` must use one of the database values: `fresher`, `less_than_1_year`, `1_to_3_years`, `3_to_5_years`, or `5_plus_years`. The app may display friendlier labels while sending these values.

### 4. List available skills
`GET {{base_url}}/profile/skills`

### 5. Set worker skills
`PUT {{base_url}}/profile/skills`

```json
{
  "skill_ids": [1, 2, 10]
}
```

This replaces the worker's selected skills with the supplied list. An empty list is allowed to remove all selected skills; workers still need a skill to meet the job application completion requirement.

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


## Preferred location dropdown update

The updated worker profile stores `preferred_state`, `preferred_district`, and `preferred_area`. Run `004_worker_preferred_location.sql` after the job location migration `003_job_location_dropdowns.sql` before deploying the updated API. The mobile app loads the same authenticated location endpoints used by job creation and submits the three selected names together.

The profile API validates that the selected district belongs to the selected state and the selected area belongs to the selected district. `PUT /profile/skills` also accepts an empty `skill_ids` list so a worker can remove all previously selected skills.
