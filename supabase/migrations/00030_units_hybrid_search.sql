-- 00028_units_hybrid_search.sql
-- Upgrade inbox search from vector-only to hybrid (full-text + vector) using
-- Reciprocal Rank Fusion. Motivation: short/rare keywords like a street name
-- that appears only in context_excerpt, or in units whose embedding failed to
-- generate, were invisible to the pure-cosine RPC introduced in
-- 00016_semantic_search_rpc.sql. Canonical Supabase hybrid-search pattern.

-- 1. FTS column derived from statement + context_excerpt. Generated STORED so
--    existing rows backfill on migration apply and inserts stay cheap.
ALTER TABLE information_units
  ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (
    to_tsvector(
      'english',
      coalesce(statement, '') || ' ' || coalesce(context_excerpt, '')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_units_fts
  ON information_units USING gin (fts);

-- 2. Replace semantic_search_units with a hybrid version. Name preserved so
--    the units Edge Function call site only gains a new parameter.
--
--    Signature change requires DROP + CREATE (Postgres rejects OR REPLACE when
--    return columns or parameter defaults change).
DROP FUNCTION IF EXISTS semantic_search_units(vector, uuid, uuid, int);

CREATE OR REPLACE FUNCTION semantic_search_units(
  p_embedding  vector(1536) DEFAULT NULL,  -- nullable: FTS-only fallback
  p_user_id    UUID         DEFAULT NULL,
  p_project_id UUID         DEFAULT NULL,
  p_limit      INT          DEFAULT 20,
  p_query_text TEXT         DEFAULT NULL,  -- new: enables keyword matching
  p_rrf_k      INT          DEFAULT 50
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
  WITH
  -- Full-text branch. websearch_to_tsquery handles quoted phrases, OR, and
  -- negation naturally. NULL query_text degenerates to "no FTS hits".
  fulltext AS (
    SELECT
      u.id,
      row_number() OVER (
        ORDER BY ts_rank_cd(u.fts, websearch_to_tsquery('english', p_query_text)) DESC
      ) AS rank_ix
    FROM information_units u
    WHERE u.user_id = p_user_id
      AND (p_project_id IS NULL OR u.project_id = p_project_id)
      AND p_query_text IS NOT NULL
      AND p_query_text <> ''
      AND u.fts @@ websearch_to_tsquery('english', p_query_text)
    ORDER BY rank_ix
    LIMIT greatest(p_limit, 1) * 2
  ),
  -- Semantic branch. NULL embedding degenerates to "no semantic hits". Units
  -- without embeddings are skipped here but remain findable via the FTS branch.
  semantic AS (
    SELECT
      u.id,
      row_number() OVER (
        ORDER BY u.embedding <=> p_embedding
      ) AS rank_ix
    FROM information_units u
    WHERE u.user_id = p_user_id
      AND (p_project_id IS NULL OR u.project_id = p_project_id)
      AND p_embedding IS NOT NULL
      AND u.embedding IS NOT NULL
    ORDER BY rank_ix
    LIMIT greatest(p_limit, 1) * 2
  ),
  merged AS (
    SELECT
      coalesce(f.id, s.id) AS id,
      coalesce(1.0 / (p_rrf_k + f.rank_ix), 0.0) +
        coalesce(1.0 / (p_rrf_k + s.rank_ix), 0.0) AS rrf_score
    FROM fulltext f
    FULL OUTER JOIN semantic s ON s.id = f.id
  )
  SELECT
    u.id,
    u.statement,
    u.context_excerpt,
    u.type AS unit_type,
    u.occurred_at,
    u.extracted_at,
    u.project_id,
    m.rrf_score::REAL AS similarity
  FROM merged m
  JOIN information_units u ON u.id = m.id
  WHERE u.user_id = p_user_id
  ORDER BY m.rrf_score DESC
  LIMIT p_limit;
$$;
