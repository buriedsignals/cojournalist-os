-- 00013_phase1_backfill.sql
-- Idempotent backfill: one "Inbox" default project per user; link existing scouts
-- and information_units to it when they lack a project_id.
-- On fresh DB this is a no-op. On Plan 5 (existing data loaded) it becomes meaningful.

-- Create one "Inbox" default project per existing user
INSERT INTO projects (user_id, name, is_default)
SELECT DISTINCT user_id, 'Inbox', TRUE FROM scouts
ON CONFLICT (user_id, name) DO NOTHING;

-- Attach any scout with NULL project_id to its owner's Inbox
UPDATE scouts s
SET project_id = p.id
FROM projects p
WHERE p.user_id = s.user_id
  AND p.is_default = TRUE
  AND s.project_id IS NULL;

-- Cascade: any information_units with NULL project_id inherit from scout
UPDATE information_units u
SET project_id = s.project_id
FROM scouts s
WHERE s.id = u.scout_id
  AND u.project_id IS NULL;
