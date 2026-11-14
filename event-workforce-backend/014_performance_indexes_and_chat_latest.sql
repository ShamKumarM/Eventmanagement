-- 014: performance indexes and one-row-per-chat latest-message view.
-- Run once in the Supabase SQL Editor. Safe to re-run.

-- Worker profile / skills / social lookups.
create index if not exists worker_profile_skills_user_idx
    on public.worker_profile_skills (user_id, skill_id);

create index if not exists employer_follows_employer_created_idx
    on public.employer_follows (employer_id, created_at desc);

create index if not exists worker_follow_requests_requester_pending_idx
    on public.worker_follow_requests (requester_id, recipient_id)
    where status = 'pending';

-- Worker chat list and message history.
create index if not exists worker_chats_low_last_message_idx
    on public.worker_chats (worker_low, last_message_at desc);

create index if not exists worker_chats_high_last_message_idx
    on public.worker_chats (worker_high, last_message_at desc);

create index if not exists worker_chat_messages_chat_created_idx
    on public.worker_chat_messages (chat_id, created_at desc);

-- Main worker feed, employer dashboard, applications, and reactions.
create index if not exists jobs_open_feed_idx
    on public.jobs (job_date, start_time)
    where status = 'open';

create index if not exists jobs_employer_created_idx
    on public.jobs (employer_id, created_at desc);

create index if not exists applications_worker_created_idx
    on public.applications (worker_id, created_at desc);

create index if not exists applications_job_created_idx
    on public.applications (job_id, created_at desc);

create index if not exists applications_job_status_idx
    on public.applications (job_id, status);

create index if not exists job_reactions_job_idx
    on public.job_reactions (job_id);

create index if not exists location_districts_state_active_idx
    on public.location_districts (state_id, is_active, name);

create index if not exists location_areas_district_active_idx
    on public.location_areas (district_id, is_active, name);

-- Latest message per chat; the API filters this view by a page of chat IDs.
create or replace view public.worker_chat_latest_messages as
select distinct on (m.chat_id)
       m.id, m.chat_id, m.sender_id, m.message_type, m.body,
       m.shared_job_snapshot, m.created_at
from public.worker_chat_messages m
order by m.chat_id, m.created_at desc, m.id desc;

grant select on public.worker_chat_latest_messages to service_role;
