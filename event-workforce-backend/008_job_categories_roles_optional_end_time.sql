-- AbiHub job category and role upgrade
-- Run once in the Supabase SQL editor after deploying the matching backend.

create table if not exists job_category_roles (
  id bigserial primary key,
  category_id integer not null references job_categories(id) on delete cascade,
  role_name text not null,
  sort_order integer not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  constraint job_category_roles_category_role_unique unique (category_id, role_name)
);

alter table job_category_roles enable row level security;
-- The backend reads this table using the service-role key. Do not expose the service key in Flutter.

-- Retire old categories from new job creation, but keep them in the table so
-- existing jobs and their category references remain valid.
update job_categories set is_active = false
where name in (
  'Catering', 'Food Serving', 'Cooking', 'Dishwashing', 'Decoration',
  'Event Decoration', 'Event Setup', 'Cleaning', 'Security',
  'Photography Assistance', 'General Event Staff', 'Welcome Staff',
  'Supervisor', 'Event Support', 'Other'
);

insert into job_categories (name, is_active) values
('Event Management', true),
('Guest Hospitality', true),
('Registration & Entry', true),
('Ushers', true),
('Security', true),
('Parking & Traffic', true),
('Promotion / Brand Activation', true),
('Exhibition / Stall', true),
('Sales & Marketing', true),
('Technical / AV', true),
('Stage Operations', true),
('Setup & Dismantling', true),
('Catering / F&B', true),
('Cleaning & Maintenance', true),
('Photography / Media', true),
('Transportation', true),
('Volunteer Team', true),
('Artist / Celebrity Support', true),
('Medical & Emergency', true),
('Specialised Event Staff', true)
on conflict (name) do update set is_active = true;

with role_seed(category_name, role_name, sort_order) as (
 values
 ('Event Management','Event Manager',1),('Event Management','Event Coordinator',2),('Event Management','Floor Manager',3),('Event Management','Event Supervisor',4),
 ('Guest Hospitality','Host/Hostess',1),('Guest Hospitality','Welcome Staff',2),('Guest Hospitality','Guest Relations',3),('Guest Hospitality','Hospitality Executive',4),
 ('Registration & Entry','Registration Staff',1),('Registration & Entry','QR Scanner Operator',2),('Registration & Entry','Ticket Checker',3),('Registration & Entry','Wristband Staff',4),
 ('Ushers','Seating Assistant',1),('Ushers','Crowd Guidance',2),('Ushers','Direction Staff',3),('Ushers','VIP Escort',4),
 ('Security','Security Guards',1),('Security','Bouncers',2),('Security','Crowd Control',3),('Security','Gate Security',4),
 ('Parking & Traffic','Parking Assistant',1),('Parking & Traffic','Valet Staff',2),('Parking & Traffic','Traffic Marshal',3),('Parking & Traffic','Vehicle Coordinator',4),
 ('Promotion / Brand Activation','Promoters',1),('Promotion / Brand Activation','Brand Ambassadors',2),('Promotion / Brand Activation','Sales Promoters',3),('Promotion / Brand Activation','Lead Generation Staff',4),
 ('Exhibition / Stall','Stall Assistant',1),('Exhibition / Stall','Booth Executive',2),('Exhibition / Stall','Product Demonstrator',3),('Exhibition / Stall','Lead Collection Staff',4),
 ('Sales & Marketing','Sales Executive',1),('Sales & Marketing','Telecaller',2),('Sales & Marketing','Field Promoter',3),('Sales & Marketing','Campaign Staff',4),
 ('Technical / AV','Sound Technician',1),('Technical / AV','Lighting Technician',2),('Technical / AV','LED Wall Operator',3),('Technical / AV','AV Technician',4),('Technical / AV','DJ',5),
 ('Stage Operations','Stage Manager',1),('Stage Operations','Backstage Coordinator',2),('Stage Operations','Stage Assistant',3),('Stage Operations','Artist Coordinator',4),
 ('Setup & Dismantling','Setup Workers',1),('Setup & Dismantling','Decoration Workers',2),('Setup & Dismantling','Stage Helpers',3),('Setup & Dismantling','Furniture Handlers',4),
 ('Catering / F&B','Servers',1),('Catering / F&B','Buffet Staff',2),('Catering / F&B','Kitchen Helpers',3),('Catering / F&B','Steward',4),('Catering / F&B','Counter Staff',5),
 ('Cleaning & Maintenance','Housekeeping',1),('Cleaning & Maintenance','Waste Collection Staff',2),('Cleaning & Maintenance','Washroom Attendant',3),
 ('Photography / Media','Photographer',1),('Photography / Media','Videographer',2),('Photography / Media','Live Streaming Operator',3),('Photography / Media','Content Creator',4),
 ('Transportation','Drivers',1),('Transportation','Guest Transport Coordinator',2),('Transportation','Logistics Assistant',3),('Transportation','Vehicle Marshal',4),
 ('Volunteer Team','Student Volunteers',1),('Volunteer Team','College Event Volunteers',2),('Volunteer Team','Community Volunteers',3),
 ('Artist / Celebrity Support','Artist Coordinator',1),('Artist / Celebrity Support','Green Room Assistant',2),('Artist / Celebrity Support','Artist Escort',3),('Artist / Celebrity Support','Runner',4),
 ('Medical & Emergency','First-Aid Staff',1),('Medical & Emergency','Nurse',2),('Medical & Emergency','Ambulance Coordinator',3),('Medical & Emergency','Emergency Response Staff',4),
 ('Specialised Event Staff','Emcee/Anchor',1),('Specialised Event Staff','DJ',2),('Specialised Event Staff','Dancers',3),('Specialised Event Staff','Performers',4),('Specialised Event Staff','Mascots',5),('Specialised Event Staff','Kids Activity Staff',6)
)
insert into job_category_roles(category_id, role_name, sort_order)
select c.id, r.role_name, r.sort_order
from role_seed r join job_categories c on c.name = r.category_name
on conflict (category_id, role_name) do update
set sort_order = excluded.sort_order, is_active = true;

-- Event end time is optional; existing records remain unchanged.
alter table jobs alter column end_time drop not null;
