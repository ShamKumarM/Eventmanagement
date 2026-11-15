# Gender-aware jobs + persistent dark theme

## Supabase
1. Open Supabase SQL Editor for the project used by the API.
2. Run `017_gender_job_allocations.sql`.
3. Deploy/restart the updated FastAPI backend.

The migration adds `profiles.gender` and the three nullable job allocation columns. Existing jobs remain open to all genders because their allocation columns stay NULL.

## Backend
The API validates allocations, exposes gender in profile responses, filters the home `sections.gender` feed, prevents workers applying to a gender with no allocated positions, and enforces the same gender quota when employers select applicants.

## Flutter
The first role selection is followed by gender selection. Returning accounts with no gender are prompted once at the gate. Users can change gender in Edit Profile. Employers allocate male/female/transgender counts in Create Job; total positions are calculated from those counts.

Dark mode is available under Profile > Appearance and is saved locally on the device.

## Example allocation
- Male: 3
- Female: 5
- Transgender: 0
- Total positions: 8

The Flutter app sends all four values and the backend rejects a total that does not equal the sum of the gender allocations.
