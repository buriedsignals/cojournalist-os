-- ============================================================
-- Add opt-in toggle for the weekly scout-health-monitor digest.
--
-- Default TRUE so existing users keep receiving the digest. Users can flip the
-- flag via the preferences UI. scout-health-monitor filters paused-scout
-- owners against this column at send-time; a missing user_preferences row is
-- treated as opt-in (DB default handles new users).
-- ============================================================

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS health_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE;
