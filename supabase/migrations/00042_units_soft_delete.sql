-- Soft-delete information units instead of hard-deleting them so agents can
-- mutate unit lifecycle safely without destroying audit history.

ALTER TABLE information_units
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS deleted_by UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS deletion_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_units_active_recent
  ON information_units (user_id, COALESCE(last_seen_at, extracted_at) DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_units_active_state
  ON information_units (user_id, verified, used_in_article)
  WHERE deleted_at IS NULL;
