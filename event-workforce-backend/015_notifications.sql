-- 015: in-app notifications for application and worker-connection events.
-- Run after migrations 001-014 in the Supabase SQL editor.
create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    type text not null check (type in (
        'application_accepted',
        'connection_request_accepted'
    )),
    title text not null,
    body text not null,
    data jsonb not null default '{}'::jsonb,
    is_read boolean not null default false,
    read_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists notifications_user_created_idx
    on public.notifications(user_id, created_at desc);
create index if not exists notifications_user_unread_idx
    on public.notifications(user_id, created_at desc)
    where is_read = false;
alter table public.notifications enable row level security;
revoke all on public.notifications from anon, authenticated;
grant select, insert, update, delete on public.notifications to service_role;

create or replace function public.notifications_set_read_at()
returns trigger language plpgsql as $$
begin
    if new.is_read and not old.is_read then
        new.read_at = now();
    elsif not new.is_read then
        new.read_at = null;
    end if;
    return new;
end $$;
drop trigger if exists notifications_set_read_at on public.notifications;
create trigger notifications_set_read_at
before update of is_read on public.notifications
for each row execute function public.notifications_set_read_at();
