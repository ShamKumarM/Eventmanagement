-- 011: consolidate worker social + employer follow into one Socialism module.
-- Apply after 009_worker_social.sql and 010_employer_follow_and_contact_access.sql.
-- Keeps employer_follows, employer_follower_counts, worker_chats and messages.
-- Converts existing accepted worker friendships into mutual follows before retiring old tables.

create table if not exists public.worker_follows (
    follower_id uuid not null references auth.users(id) on delete cascade,
    followed_id uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (follower_id, followed_id),
    constraint worker_follows_not_self check (follower_id <> followed_id)
);

-- Preserve every existing accepted friendship as a mutual follow.
insert into public.worker_follows (follower_id, followed_id, created_at)
select worker_low, worker_high, created_at from public.worker_friendships
on conflict (follower_id, followed_id) do nothing;

insert into public.worker_follows (follower_id, followed_id, created_at)
select worker_high, worker_low, created_at from public.worker_friendships
on conflict (follower_id, followed_id) do nothing;

create index if not exists worker_follows_followed_idx
    on public.worker_follows (followed_id, created_at desc);
create index if not exists worker_follows_follower_idx
    on public.worker_follows (follower_id, created_at desc);

create or replace function public.socialism_worker_follow_roles()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    if not exists (
        select 1 from public.profiles
        where id = new.follower_id and role = 'worker' and role_selected = true
    ) then
        raise exception 'only_workers_can_follow';
    end if;
    if not exists (
        select 1 from public.profiles
        where id = new.followed_id and role = 'worker' and role_selected = true
    ) then
        raise exception 'workers_can_only_follow_workers';
    end if;
    return new;
end $$;
revoke all on function public.socialism_worker_follow_roles() from public, anon, authenticated;

drop trigger if exists worker_follows_enforce_roles on public.worker_follows;
create trigger worker_follows_enforce_roles
before insert on public.worker_follows
for each row execute function public.socialism_worker_follow_roles();

alter table public.worker_follows enable row level security;
revoke all on public.worker_follows from anon, authenticated;
grant select, insert, update, delete on public.worker_follows to service_role;

-- Employer follows remain worker -> employer only. The existing role trigger from
-- 010_employer_follow_and_contact_access.sql continues to enforce this invariant.
-- Contact-request/message-to-employer functionality is intentionally removed.
drop table if exists public.employer_contact_requests cascade;
drop type if exists public.contact_request_status cascade;

-- The unified API now uses one-way follows. Chat access is granted only when
-- both workers follow one another; the existing chat history is retained.
drop function if exists public.respond_to_worker_friend_request(uuid, uuid, text);
drop table if exists public.worker_friend_requests cascade;
drop table if exists public.worker_friendships cascade;
