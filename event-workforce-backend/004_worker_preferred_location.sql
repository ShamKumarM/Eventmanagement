-- Run in Supabase SQL Editor before deploying the updated profile API.
-- Stores the complete worker preference hierarchy instead of only a free-text area.
ALTER TABLE public.worker_profiles
    ADD COLUMN IF NOT EXISTS preferred_state text,
    ADD COLUMN IF NOT EXISTS preferred_district text;

-- Keep the existing Coimbatore-wide preference selectable for older accounts.
INSERT INTO public.location_areas (district_id, name)
SELECT d.id, 'Coimbatore'
FROM public.location_districts d
JOIN public.location_states s ON s.id = d.state_id
WHERE s.name = 'Tamil Nadu' AND d.name = 'Coimbatore'
ON CONFLICT (district_id, name) DO NOTHING;

-- Backfill existing Coimbatore-area preferences so the mobile dropdown can reopen
-- with a valid state and district selected after the first app update.
UPDATE public.worker_profiles
SET preferred_state = COALESCE(preferred_state, 'Tamil Nadu'),
    preferred_district = COALESCE(preferred_district, 'Coimbatore')
WHERE preferred_area IS NOT NULL
  AND (preferred_state IS NULL OR preferred_district IS NULL);
