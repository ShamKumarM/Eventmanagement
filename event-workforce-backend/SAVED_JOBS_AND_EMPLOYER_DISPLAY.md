# Saved jobs and employer display update

## Flutter changes
- Removed the top-right heart/favourite affordance from job cards and replaced it with a bookmark/save control.
- Added a worker navigation destination called **Saved jobs**.
- Saved job IDs are stored locally using SharedPreferences; this requires no database migration or new backend endpoint.
- The Saved jobs page fetches the current job details from `GET /jobs/{job_id}` and omits jobs that are no longer available.
- Added selectable quick-filter chips below the home search field: All jobs, Fresh jobs, Higher pay, and Event date.
- The chips map to the existing recommendation sort modes (`date`, `recent`, and `pay`).
- Added a full-width pale gradient panel around the search and quick tags, fading to white below.
- Added a personalised Recommended for you row before skill/category-specific job rows.
- Shortened the bottom navigation bar, softened its top corners, and added a subtle gradient; the selected destination uses the theme indicator.

## Backend changes
- Job feed, job detail, employer job list, and home recommendations now include `employer_name`.
- Employer organisation name is preferred; the profile full name is used as a fallback.
- No database migration is required for employer name enrichment or local saved jobs.

## Note
Saved jobs are currently stored on the device. They will not automatically sync across multiple devices or reinstalls. Cross-device saved jobs would require a server-side saved-jobs table and API.
