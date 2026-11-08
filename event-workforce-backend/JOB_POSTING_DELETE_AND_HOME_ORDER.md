# Job home ordering, banner rotation and delete action

## API
- Added `DELETE /jobs/{job_id}`.
- Employer authentication and ownership are checked before deletion.
- The endpoint physically deletes the job row. If the database has restrictive foreign-key references (for example, application history), it returns HTTP 409 and instructs the employer to close/cancel the job rather than silently deleting linked history.

## Flutter
- Worker home row order is now:
  1. Recommended for you
  2. Opportunities near you
  3. Roles matching your experience
  4. Jobs matching your profile skills
  5. Job-category-specific rows
- Category rows are grouped from the available `all_jobs` recommendation list using each job's `job_categories.name`.
- The purple banner rotates through four headline/subtitle pairs every three seconds using a fade-and-slide transition.
- Employer Manage Jobs cards now include a Delete action with a confirmation dialog. It calls `DELETE /jobs/{job_id}` and refreshes the list after success.
