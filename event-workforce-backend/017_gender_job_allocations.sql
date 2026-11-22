-- Gigscart gender identity and gender-specific job allocations.
-- Run once in the Supabase SQL Editor before deploying the updated API.

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS gender text;

ALTER TABLE public.profiles
  DROP CONSTRAINT IF EXISTS profiles_gender_check;

ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_gender_check
  CHECK (gender IS NULL OR gender IN ('male', 'female', 'trans'));

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS male_required integer,
  ADD COLUMN IF NOT EXISTS female_required integer,
  ADD COLUMN IF NOT EXISTS trans_required integer;

ALTER TABLE public.jobs
  DROP CONSTRAINT IF EXISTS jobs_gender_allocation_check;

ALTER TABLE public.jobs
  ADD CONSTRAINT jobs_gender_allocation_check
  CHECK (
    (male_required IS NULL AND female_required IS NULL AND trans_required IS NULL)
    OR (
      male_required IS NOT NULL AND female_required IS NOT NULL AND trans_required IS NOT NULL
      AND male_required >= 0 AND female_required >= 0 AND trans_required >= 0
      AND male_required + female_required + trans_required = workers_required
      AND male_required + female_required + trans_required > 0
    )
  );

COMMENT ON COLUMN public.profiles.gender IS
  'User-provided gender identity: male, female, or trans.';
COMMENT ON COLUMN public.jobs.male_required IS 'Number of male positions allocated to this job.';
COMMENT ON COLUMN public.jobs.female_required IS 'Number of female positions allocated to this job.';
COMMENT ON COLUMN public.jobs.trans_required IS 'Number of other-gender positions allocated to this job.';

-- Existing jobs retain NULL allocations and remain open to all genders.
