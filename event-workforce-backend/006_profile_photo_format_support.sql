-- Run after 005_profile_photos.sql in the same Supabase project.
-- The API normalizes source photos to JPEG after decoding them, so users can
-- upload PNG, WebP, GIF, BMP, TIFF and other formats supported by Pillow.
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS avatar_url text;

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'profile-photos',
  'profile-photos',
  true,
  15728640,
  ARRAY['image/jpeg']
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;
