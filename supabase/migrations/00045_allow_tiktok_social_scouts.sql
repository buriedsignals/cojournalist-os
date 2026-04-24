-- Allow TikTok as a first-class social scout platform.
-- The UI and edge functions already support it; the original table check
-- constraint never got updated, so inserts could fail at the database layer.

ALTER TABLE scouts
DROP CONSTRAINT IF EXISTS scouts_platform_check;

ALTER TABLE scouts
ADD CONSTRAINT scouts_platform_check
CHECK (platform IN ('instagram', 'x', 'facebook', 'tiktok'));
