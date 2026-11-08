-- AbiHub job reactions + automatic removal of completed event postings.
-- Run once in the Supabase SQL Editor. The backend uses its service-role key.

create table if not exists public.job_reactions (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null references public.jobs(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    vote smallint not null check (vote in (-1, 1)),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint job_reactions_one_per_user unique (job_id, user_id)
);

create index if not exists job_reactions_job_vote_idx
    on public.job_reactions(job_id, vote);

alter table public.job_reactions enable row level security;
-- No client-side policies: reactions are read/written through authenticated
-- FastAPI endpoints, which use the service-role key on the server only.

-- Expired jobs are hard-deleted after their scheduled end time (IST), including overnight events.
-- Associated applications are deleted first so the cleanup works even if the
-- existing applications.job_id FK does not have ON DELETE CASCADE.
create or replace function public.delete_completed_event_jobs()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    expired_ids uuid[];
    removed_count integer := 0;
begin
    select array_agg(id)
      into expired_ids
      from public.jobs
     where (
        job_date + end_time
        + case when end_time <= start_time then interval '1 day' else interval '0' end
     ) < (now() at time zone 'Asia/Kolkata');

    if expired_ids is null or cardinality(expired_ids) = 0 then
        return 0;
    end if;

    delete from public.applications
     where job_id = any(expired_ids);

    -- job_reactions are removed by their ON DELETE CASCADE FK.
    delete from public.jobs
     where id = any(expired_ids);

    get diagnostics removed_count = row_count;
    return removed_count;
end;
$$;

-- Supabase projects support pg_cron when the extension is enabled.
create extension if not exists pg_cron;

-- Run daily at 18:45 UTC = 00:15 India Standard Time.
do $$
declare
    existing_job_id bigint;
begin
    select jobid into existing_job_id
      from cron.job
     where jobname = 'abihub-delete-completed-event-jobs'
     limit 1;

    if existing_job_id is not null then
        perform cron.unschedule(existing_job_id);
    end if;

    perform cron.schedule(
        'abihub-delete-completed-event-jobs',
        '45 18 * * *',
        'select public.delete_completed_event_jobs();'
    );
end;
$$;
