-- ============================================================
-- Drop user_preferences.notification_email column.
--
-- Policy decision (2026-04-20): emails are never stored outside auth.users.
-- `scout-health-monitor` now fetches the owner's email at send-time via
-- auth.admin.getUserById, matching the per-run scout notification pattern
-- (production parity — no denormalized email copy anywhere in public.*).
-- ============================================================

ALTER TABLE user_preferences
    DROP COLUMN IF EXISTS notification_email;
