-- 00018_reflection_search_rpc.sql
-- Cosine-similarity search over reflections.embedding, scoped to caller.

CREATE OR REPLACE FUNCTION semantic_search_reflections(
  p_embedding  vector(1536),
  p_user_id    UUID,
  p_project_id UUID DEFAULT NULL,
  p_limit      INT  DEFAULT 20
)
RETURNS TABLE (
  id                UUID,
  scope_description TEXT,
  content           TEXT,
  project_id        UUID,
  time_range_start  TIMESTAMPTZ,
  time_range_end    TIMESTAMPTZ,
  generated_by      TEXT,
  created_at        TIMESTAMPTZ,
  similarity        REAL
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT
    r.id,
    r.scope_description,
    r.content,
    r.project_id,
    r.time_range_start,
    r.time_range_end,
    r.generated_by,
    r.created_at,
    1 - (r.embedding <=> p_embedding) AS similarity
  FROM reflections r
  WHERE r.user_id = p_user_id
    AND r.embedding IS NOT NULL
    AND (p_project_id IS NULL OR r.project_id = p_project_id)
  ORDER BY r.embedding <=> p_embedding
  LIMIT p_limit;
$$;
