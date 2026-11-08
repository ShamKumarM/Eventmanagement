# Job reactions and automatic event-job cleanup

## What changed

- `PUT /jobs/{job_id}/reaction` accepts `{"vote": 1}`, `{"vote": -1}`, or `{"vote": 0}`.
  - `1` = like
  - `-1` = dislike
  - `0` = remove the signed-in user's reaction
- Job feed, job detail, employer job list and home recommendations now return:
  - `likes_count`
  - `dislikes_count`
  - `my_reaction` (`1`, `-1`, or `null`)
- Each account can have one reaction per job. Changing from like to dislike updates the existing row.
- The SQL migration creates a private `job_reactions` table and schedules a daily cleanup at 00:15 IST.
- Cleanup deletes jobs after their scheduled end time. Overnight jobs (end time earlier than or equal to start time) are retained until the next day's end time has passed.
- The cleanup removes related application rows before deleting a job. This means applications for a job that is permanently deleted are also removed.

## Deployment steps

1. Open the Supabase project SQL Editor.
2. Run `007_job_reactions_and_expiry_cleanup.sql` once.
3. Deploy the updated FastAPI backend.
4. Deploy the updated Flutter APK.

The app never receives the Supabase service-role key. All reaction reads/writes happen through FastAPI.

## Verify in Supabase

```sql
select jobname, schedule, command
from cron.job
where jobname = 'abihub-delete-completed-event-jobs';

select job_id, vote, count(*)
from public.job_reactions
group by job_id, vote
order by job_id, vote;
```

## Verify through the API

Send an authenticated request:

```http
PUT /jobs/{job_id}/reaction
Content-Type: application/json

{"vote": 1}
```

Then request `GET /jobs/{job_id}`. The response includes the public totals and the current user's reaction.

To remove the reaction, send `{"vote": 0}`. To dislike, send `{"vote": -1}`.
