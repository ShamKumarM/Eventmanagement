-- AbiHub profile photo support.
-- Run this migration in the Supabase SQL Editor for the project used by the API.
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS avatar_url text;

-- The API uses the service-role key to upload; public read access is intended
-- only for profile images. Do not store identity or verification documents here.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'profile-photos',
  'profile-photos',
  true,
  3145728,
  ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE
SET public = true,
    file_size_limit = 3145728,
    allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp'];
