-- Run in Supabase SQL editor.
create table if not exists job_categories (
  id serial primary key,
  name text unique not null,
  is_active boolean not null default true
);

insert into job_categories (name) values
  ('Catering'), ('Decoration'), ('Security'),
  ('Welcome Staff'), ('Supervisor'), ('Event Support'), ('Other')
on conflict (name) do nothing;

do $$ begin
  create type job_status as enum
    ('draft','open','filled','in_progress','completed','cancelled','expired');
exception when duplicate_object then null; end $$;

do $$ begin
  create type payment_type as enum ('spot_pay','two_days','custom_days','other');
exception when duplicate_object then null; end $$;

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  employer_id uuid not null references auth.users(id),
  title text not null,
  category_id int not null references job_categories(id),
  category_other text,
  description text,

  job_date date not null,
  reporting_time time not null,
  start_time time not null,
  end_time time not null,          -- end_time <= start_time means "next day"

  workers_required int not null check (workers_required > 0),
  salary_per_worker numeric(10,2) not null check (salary_per_worker > 0),
  payment_type payment_type not null,
  payment_days int check (payment_days > 0),
  payment_note text,

  venue_name text not null,
  address text not null,
  area text not null,
  city text not null default 'Coimbatore',
  latitude double precision,
  longitude double precision,
  maps_url text,

  food_provided boolean not null default false,
  transport_provided boolean not null default false,
  dress_code text,

  status job_status not null default 'open',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint payment_days_required
    check (payment_type <> 'custom_days' or payment_days is not null)
);

create index if not exists jobs_feed_idx on jobs (status, job_date);
create index if not exists jobs_employer_idx on jobs (employer_id);
create index if not exists jobs_area_idx on jobs (area);
create index if not exists jobs_category_idx on jobs (category_id);

-- Backend uses the service-role key (bypasses RLS). With RLS on and no
-- policies, direct access from the anon key is denied.
alter table job_categories enable row level security;
alter table jobs enable row level security;
