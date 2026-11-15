-- Gigscart worker skills catalogue expansion
-- Safe to run more than once. Existing worker_profile_skills rows are not changed.
-- Run this in the Supabase SQL Editor for the project used by the backend.

INSERT INTO public.skills (name, is_active)
VALUES
    ('Event Manager', TRUE),
    ('Event Coordinator', TRUE),
    ('Floor Manager', TRUE),
    ('Event Supervisor', TRUE),
    ('Host/Hostess', TRUE),
    ('Welcome Staff', TRUE),
    ('Guest Relations', TRUE),
    ('Hospitality Executive', TRUE),
    ('Registration Staff', TRUE),
    ('QR Scanner Operator', TRUE),
    ('Ticket Checker', TRUE),
    ('Wristband Staff', TRUE),
    ('Seating Assistant', TRUE),
    ('Crowd Guidance Staff', TRUE),
    ('Direction Staff', TRUE),
    ('VIP Escort', TRUE),
    ('Security Guard', TRUE),
    ('Bouncer', TRUE),
    ('Crowd Control Staff', TRUE),
    ('Gate Security', TRUE),
    ('Parking Assistant', TRUE),
    ('Valet Staff', TRUE),
    ('Traffic Marshal', TRUE),
    ('Vehicle Coordinator', TRUE),
    ('Promoter', TRUE),
    ('Brand Ambassador', TRUE),
    ('Sales Promoter', TRUE),
    ('Lead Generation Staff', TRUE),
    ('Stall Assistant', TRUE),
    ('Booth Executive', TRUE),
    ('Product Demonstrator', TRUE),
    ('Lead Collection Staff', TRUE),
    ('Sales Executive', TRUE),
    ('Telecaller', TRUE),
    ('Field Promoter', TRUE),
    ('Campaign Staff', TRUE),
    ('Sound Technician', TRUE),
    ('Lighting Technician', TRUE),
    ('LED Wall Operator', TRUE),
    ('AV Technician', TRUE),
    ('DJ', TRUE),
    ('Stage Manager', TRUE),
    ('Backstage Coordinator', TRUE),
    ('Stage Assistant', TRUE),
    ('Artist Coordinator', TRUE),
    ('Setup Worker', TRUE),
    ('Decoration Worker', TRUE),
    ('Stage Helper', TRUE),
    ('Furniture Handler', TRUE),
    ('Server', TRUE),
    ('Buffet Staff', TRUE),
    ('Kitchen Helper', TRUE),
    ('Steward', TRUE),
    ('Counter Staff', TRUE),
    ('Housekeeping Staff', TRUE),
    ('Waste Collection Staff', TRUE),
    ('Washroom Attendant', TRUE),
    ('Photographer', TRUE),
    ('Videographer', TRUE),
    ('Live Streaming Operator', TRUE),
    ('Content Creator', TRUE),
    ('Driver', TRUE),
    ('Guest Transport Coordinator', TRUE),
    ('Logistics Assistant', TRUE),
    ('Vehicle Marshal', TRUE),
    ('Student Volunteer', TRUE),
    ('College Event Volunteer', TRUE),
    ('Community Volunteer', TRUE),
    ('Green Room Assistant', TRUE),
    ('Artist Escort', TRUE),
    ('Runner', TRUE),
    ('First-Aid Staff', TRUE),
    ('Nurse', TRUE),
    ('Ambulance Coordinator', TRUE),
    ('Emergency Response Staff', TRUE),
    ('Emcee/Anchor', TRUE),
    ('Dancer', TRUE),
    ('Performer', TRUE),
    ('Mascot', TRUE),
    ('Kids Activity Staff', TRUE)
ON CONFLICT (name)
DO UPDATE SET is_active = TRUE;

-- Verify the catalogue and active count.
SELECT COUNT(*) AS active_skill_count
FROM public.skills
WHERE is_active = TRUE;

-- Review all active skills.
SELECT id, name
FROM public.skills
WHERE is_active = TRUE
ORDER BY id;
