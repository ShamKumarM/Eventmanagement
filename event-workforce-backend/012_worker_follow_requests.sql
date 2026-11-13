-- 012: worker follow requests and public follower counts.
-- Workers request to connect; the recipient accepts to create a mutual follow.
-- Employers remain follow-only targets and never receive requests or chat access.

create table if not exists public.worker_follow_requests (
    id uuid primary key default gen_random_uuid(),
    requester_id uuid not null references auth.users(id) on delete cascade,
    recipient_id uuid not null references auth.users(id) on delete cascade,
    status text not null default 'pending'
        check (status in ('pending', 'accepted', 'declined', 'cancelled')),
    created_at timestamptz not null default now(),
    responded_at timestamptz,
    constraint worker_follow_requests_not_self check (requester_id <> recipient_id)
);

create unique index if not exists worker_follow_requests_one_pending
    on public.worker_follow_requests(requester_id, recipient_id)
    where status = 'pending';
create index if not exists worker_follow_requests_recipient_idx
    on public.worker_follow_requests(recipient_id, created_at desc)
    where status = 'pending';

create or replace function public.socialism_follow_request_roles()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    if not exists (
        select 1 from public.profiles
        where id = new.requester_id and role = 'worker' and role_selected = true
    ) then
        raise exception 'only_workers_can_send_follow_requests';
    end if;
    if not exists (
        select 1 from public.profiles
        where id = new.recipient_id and role = 'worker' and role_selected = true
    ) then
        raise exception 'follow_requests_are_worker_only';
    end if;
    return new;
end $$;
revoke all on function public.socialism_follow_request_roles() from public, anon, authenticated;
drop trigger if exists worker_follow_requests_enforce_roles on public.worker_follow_requests;
create trigger worker_follow_requests_enforce_roles
before insert or update on public.worker_follow_requests
for each row execute function public.socialism_follow_request_roles();

alter table public.worker_follow_requests enable row level security;
revoke all on public.worker_follow_requests from anon, authenticated;
grant select, insert, update, delete on public.worker_follow_requests to service_role;

create or replace view public.worker_follower_counts as
select p.id as worker_id, count(f.follower_id)::bigint as follower_count
from public.profiles p
left join public.worker_follows f on f.followed_id = p.id
where p.role = 'worker' and p.role_selected = true
group by p.id;

grant select on public.worker_follower_counts to service_role;
