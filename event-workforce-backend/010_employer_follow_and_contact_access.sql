-- 010: employer follows + contact-access requests + follower-count view.
-- Run in the Supabase SQL Editor AFTER 001, 002 and the employer verification tables exist.
-- Safe to re-run. Verification itself is NOT changed here: it already lives in
-- employer_profiles.verification_status and is reviewed through /admin/employer-verifications.

-- ---------------------------------------------------------------- follows
create table if not exists public.employer_follows (
    worker_id   uuid not null references auth.users(id) on delete cascade,
    employer_id uuid not null references auth.users(id) on delete cascade,
    created_at  timestamptz not null default now(),
    primary key (worker_id, employer_id),                 -- one follow per worker per employer
    constraint employer_follows_not_self check (worker_id <> employer_id)
);
create index if not exists employer_follows_employer_idx
    on public.employer_follows (employer_id, created_at desc);

-- ------------------------------------------------------ contact requests
do $$ begin
    create type public.contact_request_status as enum
        ('pending', 'accepted', 'rejected', 'cancelled', 'revoked');
exception when duplicate_object then null; end $$;

create table if not exists public.employer_contact_requests (
    id           uuid primary key default gen_random_uuid(),
    worker_id    uuid not null references auth.users(id) on delete cascade,
    employer_id  uuid not null references auth.users(id) on delete cascade,
    status       public.contact_request_status not null default 'pending',
    message      text check (message is null or char_length(message) <= 300),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    responded_at timestamptz,
    constraint employer_contact_requests_not_self check (worker_id <> employer_id)
);

-- At most ONE active (pending or accepted) request per worker/employer pair.
-- Rejected / cancelled / revoked rows are history and do not block a new request.
create unique index if not exists employer_contact_requests_one_active_per_pair
    on public.employer_contact_requests (worker_id, employer_id)
    where status in ('pending', 'accepted');
create index if not exists employer_contact_requests_employer_idx
    on public.employer_contact_requests (employer_id, status, created_at desc);
create index if not exists employer_contact_requests_worker_idx
    on public.employer_contact_requests (worker_id, created_at desc);

create or replace function public.employer_contact_requests_touch()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

drop trigger if exists employer_contact_requests_touch on public.employer_contact_requests;
create trigger employer_contact_requests_touch
before update on public.employer_contact_requests
for each row execute function public.employer_contact_requests_touch();

-- ------------------------------------- defence in depth: roles are checked in the DB too
create or replace function public.employer_follow_enforce_roles()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    if not exists (select 1 from public.profiles
                   where id = new.worker_id and role = 'worker' and role_selected) then
        raise exception 'worker_role_required';
    end if;
    if not exists (select 1 from public.profiles
                   where id = new.employer_id and role = 'employer' and role_selected) then
        raise exception 'employer_role_required';
    end if;
    return new;
end $$;
revoke all on function public.employer_follow_enforce_roles() from public, anon, authenticated;

drop trigger if exists employer_follows_enforce_roles on public.employer_follows;
create trigger employer_follows_enforce_roles
before insert on public.employer_follows
for each row execute function public.employer_follow_enforce_roles();

drop trigger if exists employer_contact_requests_enforce_roles on public.employer_contact_requests;
create trigger employer_contact_requests_enforce_roles
before insert on public.employer_contact_requests
for each row execute function public.employer_follow_enforce_roles();

-- ---------------------------------------- follower counts (popularity, NOT verification)
-- "verified" is copied from the admin-controlled verification_status; follower_count never
-- influences it and it never influences follower_count.
create or replace view public.employer_follower_counts
with (security_invoker = true) as
select f.employer_id,
       count(*)::int as follower_count,
       coalesce(ep.verification_status::text = 'approved', false) as verified
from public.employer_follows f
left join public.employer_profiles ep on ep.user_id = f.employer_id
group by f.employer_id, ep.verification_status;

-- ------------------------------------------------ lock everything to the backend only
alter table public.employer_follows          enable row level security;
alter table public.employer_contact_requests enable row level security;
revoke all on public.employer_follows          from anon, authenticated;
revoke all on public.employer_contact_requests from anon, authenticated;
revoke all on public.employer_follower_counts  from anon, authenticated;
grant select, insert, update, delete on public.employer_follows          to service_role;
grant select, insert, update, delete on public.employer_contact_requests to service_role;
grant select on public.employer_follower_counts to service_role;
-- No RLS policies on purpose: browsers/anon keys cannot read or write these tables.
