-- 00019_scout_rpcs.sql
-- Dedup check for web / beat extraction; failure counter for auto-pause.

-- Returns true if an information_unit with embedding within `threshold`
-- cosine distance exists for this scout within the last `days` days.
CREATE OR REPLACE FUNCTION check_unit_dedup(
  p_embedding  vector(1536),
  p_scout_id   UUID,
  p_threshold  REAL DEFAULT 0.85,
  p_days       INT  DEFAULT 90
)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1
    FROM information_units u
    WHERE u.scout_id = p_scout_id
      AND u.embedding IS NOT NULL
      AND u.extracted_at >= NOW() - make_interval(days => p_days)
      AND (1 - (u.embedding <=> p_embedding)) >= p_threshold
  );
$$;

-- Increment consecutive_failures and flip is_active to false at threshold.
-- Caller is the execute-scout dispatcher or a worker after a failed run.
CREATE OR REPLACE FUNCTION increment_scout_failures(
  p_scout_id  UUID,
  p_threshold INT DEFAULT 3
)
RETURNS TABLE (consecutive_failures INT, is_active BOOLEAN)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  RETURN QUERY
  UPDATE scouts s
  SET consecutive_failures = s.consecutive_failures + 1,
      is_active = CASE
                    WHEN s.consecutive_failures + 1 >= p_threshold THEN FALSE
                    ELSE s.is_active
                  END,
      updated_at = NOW()
  WHERE s.id = p_scout_id
  RETURNING s.consecutive_failures, s.is_active;
END; $$;

-- Reset failure counter after a successful run.
CREATE OR REPLACE FUNCTION reset_scout_failures(p_scout_id UUID)
RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  UPDATE scouts
  SET consecutive_failures = 0,
      updated_at = NOW()
  WHERE id = p_scout_id;
$$;
