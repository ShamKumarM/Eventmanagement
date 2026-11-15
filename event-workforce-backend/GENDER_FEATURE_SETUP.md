# Gigscart gender selection and gender-wise job allocation

## Database migration
Run `017_gender_job_allocations.sql` in the Supabase SQL Editor before deploying the updated backend.

- `profiles.gender`: `male`, `female`, or `trans`.
- `jobs.male_required`, `jobs.female_required`, `jobs.trans_required`: gender-wise position allocations.
- Existing jobs keep NULL allocations and remain open to all genders for backward compatibility.
- New Flutter job postings send all three counts. The database requires their sum to equal `workers_required`.

## API behaviour
- `PATCH /profile/me` accepts `gender`.
- `GET /profile/me` and `GET /auth/me` return `profile.gender`.
- `POST /jobs` accepts the three gender count fields.
- `GET /jobs/{id}` returns the allocation counts.
- `GET /recommendations/home` returns `sections.gender`, filtered to the signed-in worker's gender; legacy open-to-all jobs are included.
- Applying to a gender-allocated job requires a saved gender and a positive allocation for that gender.
- Employer selection enforces both the overall job capacity and the gender-specific allocation.

## Existing users
The Flutter gate sends accounts with a missing gender to the gender selection screen. No existing profile is assigned a gender automatically.

## Example
A job with 5 female and 3 male positions is sent as:
`workers_required=8`, `male_required=3`, `female_required=5`, `trans_required=0`.
