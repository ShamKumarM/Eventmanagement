-- Gigscart: start time is optional; reporting time remains mandatory.
-- Apply in Supabase SQL Editor before deploying the matching backend.
ALTER TABLE public.jobs
    ALTER COLUMN start_time DROP NOT NULL,
    ALTER COLUMN reporting_time SET NOT NULL;
