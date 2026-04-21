-- 00016_semantic_search_rpc.sql
-- Cosine-similarity search over information_units.embedding, scoped to the
-- caller's rows (passed explicitly as p_user_id since SECURITY DEFINER
-- bypasses RLS). The units Edge Function already calls requireUser() before
-- invoking this, so the uid supplied is the authed caller's.

CREATE OR REPLACE FUNCTION semantic_search_units(
  p_embedding  vector(1536),
  p_user_id    UUID,
  p_project_id UUID DEFAULT NULL,
  p_limit      INT  DEFAULT 20
)
RETURNS TABLE (
  id              UUID,
  statement       TEXT,
  context_excerpt TEXT,
  unit_type       TEXT,
  occurred_at     DATE,
  extracted_at    TIMESTAMPTZ,
  project_id      UUID,
  similarity      REAL
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT
    u.id,
    u.statement,
    u.context_excerpt,
    u.type AS unit_type,
    u.occurred_at,
    u.extracted_at,
    u.project_id,
    1 - (u.embedding <=> p_embedding) AS similarity
  FROM information_units u
  WHERE u.user_id = p_user_id
    AND u.embedding IS NOT NULL
    AND (p_project_id IS NULL OR u.project_id = p_project_id)
  ORDER BY u.embedding <=> p_embedding
  LIMIT p_limit;
$$;
