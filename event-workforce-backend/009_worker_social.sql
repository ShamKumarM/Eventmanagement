-- Worker connections and direct messaging. Apply after the profiles and jobs
-- tables exist. These tables have no client-side RLS policies; FastAPI accesses
-- them with the server-only service-role key after checking the caller's token.

create table if not exists public.worker_friend_requests (
    id uuid primary key default gen_random_uuid(),
    sender_id uuid not null references auth.users(id) on delete cascade,
    recipient_id uuid not null references auth.users(id) on delete cascade,
    status text not null default 'pending'
        check (status in ('pending', 'accepted', 'rejected', 'cancelled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint worker_friend_request_not_self check (sender_id <> recipient_id)
);

-- Enforce one outstanding request per pair, regardless of request direction.
create unique index if not exists worker_friend_request_one_pending_per_pair
    on public.worker_friend_requests (least(sender_id, recipient_id), greatest(sender_id, recipient_id))
    where status = 'pending';
create index if not exists worker_friend_requests_recipient_idx
    on public.worker_friend_requests (recipient_id, created_at desc)
    where status = 'pending';
create index if not exists worker_friend_requests_sender_idx
    on public.worker_friend_requests (sender_id, created_at desc)
    where status = 'pending';

create table if not exists public.worker_friendships (
    worker_low uuid not null references auth.users(id) on delete cascade,
    worker_high uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (worker_low, worker_high),
    constraint worker_friendship_canonical_pair check (worker_low < worker_high)
);
create index if not exists worker_friendships_high_idx
    on public.worker_friendships (worker_high, created_at desc);

create table if not exists public.worker_chats (
    id uuid primary key default gen_random_uuid(),
    worker_low uuid not null references auth.users(id) on delete cascade,
    worker_high uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    last_message_at timestamptz,
    constraint worker_chat_canonical_pair check (worker_low < worker_high),
    constraint worker_chat_one_per_pair unique (worker_low, worker_high)
);

create table if not exists public.worker_chat_messages (
    id uuid primary key default gen_random_uuid(),
    chat_id uuid not null references public.worker_chats(id) on delete cascade,
    sender_id uuid not null references auth.users(id) on delete cascade,
    message_type text not null check (message_type in ('text', 'job_share')),
    body text,
    shared_job_id uuid references public.jobs(id) on delete set null,
    shared_job_snapshot jsonb,
    created_at timestamptz not null default now(),
    constraint worker_chat_message_content check (
        (message_type = 'text' and body is not null and length(btrim(body)) > 0
            and shared_job_id is null and shared_job_snapshot is null)
        or
        (message_type = 'job_share' and body is null and shared_job_snapshot is not null)
    )
);
create index if not exists worker_chat_messages_chat_created_idx
    on public.worker_chat_messages (chat_id, created_at desc);

alter table public.worker_friend_requests enable row level security;
alter table public.worker_friendships enable row level security;
alter table public.worker_chats enable row level security;
alter table public.worker_chat_messages enable row level security;

create or replace function public.respond_to_worker_friend_request(
    p_request_id uuid,
    p_actor_id uuid,
    p_action text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
    v_request public.worker_friend_requests%rowtype;
    v_low uuid;
    v_high uuid;
begin
    if p_action not in ('accept', 'reject', 'cancel') then
        raise exception 'invalid_action';
    end if;

    select * into v_request
      from public.worker_friend_requests
     where id = p_request_id
     for update;

    if not found then
        raise exception 'request_not_found';
    end if;
    if v_request.status <> 'pending' then
        raise exception 'request_not_pending';
    end if;

    if p_action = 'cancel' then
        if v_request.sender_id <> p_actor_id then
            raise exception 'not_allowed';
        end if;
        update public.worker_friend_requests
           set status = 'cancelled', updated_at = now()
         where id = p_request_id
         returning * into v_request;
        return to_jsonb(v_request);
    end if;

    if v_request.recipient_id <> p_actor_id then
        raise exception 'not_allowed';
    end if;

    if p_action = 'reject' then
        update public.worker_friend_requests
           set status = 'rejected', updated_at = now()
         where id = p_request_id
         returning * into v_request;
        return to_jsonb(v_request);
    end if;

    v_low := least(v_request.sender_id, v_request.recipient_id);
    v_high := greatest(v_request.sender_id, v_request.recipient_id);
    insert into public.worker_friendships (worker_low, worker_high)
    values (v_low, v_high)
    on conflict (worker_low, worker_high) do nothing;

    insert into public.worker_chats (worker_low, worker_high)
    values (v_low, v_high)
    on conflict (worker_low, worker_high) do nothing;

    update public.worker_friend_requests
       set status = 'accepted', updated_at = now()
     where id = p_request_id
     returning * into v_request;
    return to_jsonb(v_request);
end;
$function$;

revoke all on function public.respond_to_worker_friend_request(uuid, uuid, text) from public;
revoke all on function public.respond_to_worker_friend_request(uuid, uuid, text) from anon;
revoke all on function public.respond_to_worker_friend_request(uuid, uuid, text) from authenticated;
grant execute on function public.respond_to_worker_friend_request(uuid, uuid, text) to service_role;

create or replace function public.touch_worker_chat_last_message()
returns trigger
language plpgsql
set search_path = ''
as $function$
begin
    update public.worker_chats
       set last_message_at = new.created_at
     where id = new.chat_id;
    return new;
end;
$function$;

drop trigger if exists worker_chat_messages_touch_chat on public.worker_chat_messages;
create trigger worker_chat_messages_touch_chat
after insert on public.worker_chat_messages
for each row execute function public.touch_worker_chat_last_message();
