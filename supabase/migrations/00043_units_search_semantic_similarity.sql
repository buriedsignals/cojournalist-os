-- Add semantic cosine similarity to semantic_search_units so the inbox can
-- explain hybrid-search results without guessing from the fused RRF rank.

DROP FUNCTION IF EXISTS semantic_search_units(vector, uuid, uuid, uuid, int, text, int);

CREATE OR REPLACE FUNCTION semantic_search_units(
  p_embedding  vector(1536) DEFAULT NULL,
  p_user_id    UUID         DEFAULT NULL,
  p_project_id UUID         DEFAULT NULL,
  p_scout_id   UUID         DEFAULT NULL,
  p_limit      INT          DEFAULT 20,
  p_query_text TEXT         DEFAULT NULL,
  p_rrf_k      INT          DEFAULT 50
)
RETURNS TABLE (
  id                  UUID,
  statement           TEXT,
  context_excerpt     TEXT,
  unit_type           TEXT,
  occurred_at         DATE,
  extracted_at        TIMESTAMPTZ,
  project_id          UUID,
  similarity          REAL,
  semantic_similarity REAL
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH
  scoped_units AS (
    SELECT u.*
    FROM information_units u
    WHERE u.user_id = p_user_id
      AND (
        (p_project_id IS NULL AND p_scout_id IS NULL)
        OR EXISTS (
          SELECT 1
          FROM unit_occurrences o
          WHERE o.unit_id = u.id
            AND o.user_id = p_user_id
            AND (p_project_id IS NULL OR o.project_id = p_project_id)
            AND (p_scout_id IS NULL OR o.scout_id = p_scout_id)
        )
      )
  ),
  fulltext AS (
    SELECT
      u.id,
      row_number() OVER (
        ORDER BY ts_rank_cd(u.fts, websearch_to_tsquery('english', p_query_text)) DESC
      ) AS rank_ix
    FROM scoped_units u
    WHERE p_query_text IS NOT NULL
      AND p_query_text <> ''
      AND u.fts @@ websearch_to_tsquery('english', p_query_text)
    ORDER BY rank_ix
    LIMIT greatest(p_limit, 1) * 2
  ),
  semantic AS (
    SELECT
      u.id,
      row_number() OVER (
        ORDER BY u.embedding <=> p_embedding
      ) AS rank_ix,
      (1 - (u.embedding <=> p_embedding))::REAL AS semantic_similarity
    FROM scoped_units u
    WHERE p_embedding IS NOT NULL
      AND u.embedding IS NOT NULL
    ORDER BY rank_ix
    LIMIT greatest(p_limit, 1) * 2
  ),
  merged AS (
    SELECT
      COALESCE(f.id, s.id) AS id,
      COALESCE(1.0 / (p_rrf_k + f.rank_ix), 0.0) +
        COALESCE(1.0 / (p_rrf_k + s.rank_ix), 0.0) AS rrf_score,
      s.semantic_similarity
    FROM fulltext f
    FULL OUTER JOIN semantic s ON s.id = f.id
  )
  SELECT
    u.id,
    u.statement,
    u.context_excerpt,
    u.type AS unit_type,
    u.occurred_at,
    COALESCE(u.last_seen_at, u.extracted_at) AS extracted_at,
    COALESCE(
      p_project_id,
      (
        SELECT o.project_id
        FROM unit_occurrences o
        WHERE o.unit_id = u.id
          AND o.user_id = p_user_id
          AND o.project_id IS NOT NULL
        ORDER BY o.extracted_at DESC
        LIMIT 1
      ),
      u.project_id
    ) AS project_id,
    m.rrf_score::REAL AS similarity,
    m.semantic_similarity::REAL AS semantic_similarity
  FROM merged m
  JOIN scoped_units u ON u.id = m.id
  ORDER BY m.rrf_score DESC
  LIMIT p_limit;
$$;
