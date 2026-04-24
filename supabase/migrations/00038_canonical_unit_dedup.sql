-- 00037_canonical_unit_dedup.sql
-- Canonical information-unit dedup across runs and across scouts.
--
-- Design:
--   - Keep a single canonical row in information_units per user-visible fact.
--   - Store every scout/run/source hit as provenance in unit_occurrences.
--   - Perform the match/create-or-merge decision atomically in Postgres so
--     concurrent scouts do not create parallel canonical rows.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Shared normalization helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION normalize_unit_statement(p_statement TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT NULLIF(
    regexp_replace(lower(btrim(COALESCE(p_statement, ''))), '\s+', ' ', 'g'),
    ''
  );
$$;

CREATE OR REPLACE FUNCTION normalize_source_url(p_url TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  v TEXT;
BEGIN
  IF p_url IS NULL OR btrim(p_url) = '' THEN
    RETURN NULL;
  END IF;

  v := lower(btrim(p_url));
  v := regexp_replace(v, '#.*$', '');
  v := regexp_replace(v, '/+$', '');
  v := regexp_replace(v, '\?$', '');

  RETURN NULLIF(v, '');
END;
$$;

CREATE OR REPLACE FUNCTION text_array_union(a TEXT[], b TEXT[])
RETURNS TEXT[]
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT COALESCE(
    ARRAY(
      SELECT DISTINCT trimmed
      FROM (
        SELECT NULLIF(btrim(item), '') AS trimmed
        FROM unnest(COALESCE(a, ARRAY[]::TEXT[]) || COALESCE(b, ARRAY[]::TEXT[])) AS item
      ) s
      WHERE trimmed IS NOT NULL
      ORDER BY trimmed
    ),
    ARRAY[]::TEXT[]
  );
$$;

CREATE OR REPLACE FUNCTION unit_type_rank(p_type TEXT)
RETURNS INT
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE p_type
    WHEN 'promise' THEN 4
    WHEN 'event' THEN 3
    WHEN 'fact' THEN 2
    WHEN 'entity_update' THEN 1
    ELSE 0
  END;
$$;

CREATE OR REPLACE FUNCTION canonical_unit_type(existing_type TEXT, incoming_type TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN unit_type_rank(COALESCE(incoming_type, existing_type)) >=
         unit_type_rank(COALESCE(existing_type, incoming_type))
      THEN COALESCE(incoming_type, existing_type)
    ELSE COALESCE(existing_type, incoming_type)
  END;
$$;

-- ---------------------------------------------------------------------------
-- Canonical unit schema
-- ---------------------------------------------------------------------------

ALTER TABLE information_units
  DROP CONSTRAINT IF EXISTS information_units_type_check;

ALTER TABLE information_units
  ADD CONSTRAINT information_units_type_check
  CHECK (type IN ('fact', 'event', 'entity_update', 'promise'));

ALTER TABLE information_units
  DROP CONSTRAINT IF EXISTS information_units_source_type_check;

ALTER TABLE information_units
  ADD CONSTRAINT information_units_source_type_check
  CHECK (source_type IN ('scout', 'manual_ingest', 'agent_ingest', 'civic_promise'));

ALTER TABLE information_units
  DROP CONSTRAINT IF EXISTS information_units_scout_id_fkey;

ALTER TABLE information_units
  ADD CONSTRAINT information_units_scout_id_fkey
  FOREIGN KEY (scout_id) REFERENCES scouts(id) ON DELETE SET NULL;

ALTER TABLE information_units
  ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS occurrence_count INT NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS source_count INT NOT NULL DEFAULT 1;

UPDATE information_units
SET
  first_seen_at = COALESCE(first_seen_at, extracted_at, NOW()),
  last_seen_at = COALESCE(last_seen_at, extracted_at, NOW()),
  occurrence_count = COALESCE(NULLIF(occurrence_count, 0), 1),
  source_count = COALESCE(NULLIF(source_count, 0), 1)
WHERE
  first_seen_at IS NULL
  OR last_seen_at IS NULL
  OR occurrence_count IS NULL
  OR occurrence_count = 0
  OR source_count IS NULL
  OR source_count = 0;

ALTER TABLE scout_runs
  ADD COLUMN IF NOT EXISTS merged_existing_count INT NOT NULL DEFAULT 0;

ALTER TABLE promises
  DROP CONSTRAINT IF EXISTS promises_scout_id_fkey;

ALTER TABLE promises
  ADD CONSTRAINT promises_scout_id_fkey
  FOREIGN KEY (scout_id) REFERENCES scouts(id) ON DELETE SET NULL;

ALTER TABLE promises
  ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES information_units(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_promises_user_unit
  ON promises(user_id, unit_id)
  WHERE unit_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS unit_occurrences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  unit_id UUID NOT NULL REFERENCES information_units(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  scout_id UUID REFERENCES scouts(id) ON DELETE SET NULL,
  scout_run_id UUID REFERENCES scout_runs(id) ON DELETE SET NULL,
  raw_capture_id UUID REFERENCES raw_captures(id) ON DELETE SET NULL,
  scout_type TEXT,
  source_kind TEXT NOT NULL DEFAULT 'scout'
    CHECK (source_kind IN ('scout', 'manual_ingest', 'agent_ingest', 'civic_promise')),
  source_url TEXT,
  normalized_source_url TEXT,
  source_title TEXT,
  source_domain TEXT,
  content_sha256 TEXT,
  statement_hash TEXT NOT NULL,
  occurred_at DATE,
  extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_units_user_last_seen
  ON information_units(user_id, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_unit_occurrences_unit
  ON unit_occurrences(unit_id);

CREATE INDEX IF NOT EXISTS idx_unit_occurrences_project_unit
  ON unit_occurrences(project_id, unit_id);

CREATE INDEX IF NOT EXISTS idx_unit_occurrences_scout_time
  ON unit_occurrences(scout_id, extracted_at DESC);

CREATE INDEX IF NOT EXISTS idx_unit_occurrences_user_url
  ON unit_occurrences(user_id, normalized_source_url);

CREATE INDEX IF NOT EXISTS idx_unit_occurrences_user_content_hash
  ON unit_occurrences(user_id, content_sha256);

CREATE INDEX IF NOT EXISTS idx_unit_occurrences_user_statement_hash
  ON unit_occurrences(user_id, statement_hash);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unit_occurrences_raw_capture_statement
  ON unit_occurrences(unit_id, raw_capture_id, statement_hash)
  WHERE raw_capture_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_unit_occurrences_run_url_statement
  ON unit_occurrences(unit_id, scout_run_id, normalized_source_url, statement_hash)
  WHERE raw_capture_id IS NULL
    AND scout_run_id IS NOT NULL
    AND normalized_source_url IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_unit_occurrences_run_statement
  ON unit_occurrences(unit_id, scout_run_id, statement_hash)
  WHERE raw_capture_id IS NULL
    AND scout_run_id IS NOT NULL
    AND normalized_source_url IS NULL;

ALTER TABLE unit_occurrences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS unit_occurrences_user ON unit_occurrences;
CREATE POLICY unit_occurrences_user ON unit_occurrences
  FOR ALL
  USING (user_id = (SELECT auth.uid()))
  WITH CHECK (user_id = (SELECT auth.uid()));

REVOKE INSERT, UPDATE, DELETE ON public.unit_occurrences FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- Backfill provenance from historical information_units
-- ---------------------------------------------------------------------------

INSERT INTO unit_occurrences (
  unit_id,
  user_id,
  project_id,
  scout_id,
  raw_capture_id,
  scout_type,
  source_kind,
  source_url,
  normalized_source_url,
  source_title,
  source_domain,
  content_sha256,
  statement_hash,
  occurred_at,
  extracted_at,
  metadata
)
SELECT
  u.id,
  u.user_id,
  u.project_id,
  u.scout_id,
  u.raw_capture_id,
  u.scout_type,
  COALESCE(u.source_type, 'scout'),
  u.source_url,
  normalize_source_url(u.source_url),
  u.source_title,
  u.source_domain,
  rc.content_sha256,
  encode(
    extensions.digest(COALESCE(normalize_unit_statement(u.statement), ''), 'sha256'),
    'hex'
  ),
  u.occurred_at,
  COALESCE(u.last_seen_at, u.extracted_at, NOW()),
  jsonb_build_object('backfilled_from_unit', TRUE)
FROM information_units u
LEFT JOIN raw_captures rc ON rc.id = u.raw_capture_id
WHERE u.user_id IS NOT NULL
ON CONFLICT DO NOTHING;

UPDATE information_units u
SET
  occurrence_count = COALESCE(src.occurrence_count, u.occurrence_count, 1),
  source_count = COALESCE(src.source_count, u.source_count, 1),
  first_seen_at = COALESCE(src.first_seen_at, u.first_seen_at, u.extracted_at, NOW()),
  last_seen_at = COALESCE(src.last_seen_at, u.last_seen_at, u.extracted_at, NOW())
FROM (
  SELECT
    o.unit_id,
    COUNT(*)::INT AS occurrence_count,
    COUNT(
      DISTINCT COALESCE(o.normalized_source_url, o.content_sha256, o.statement_hash)
    )::INT AS source_count,
    MIN(o.extracted_at) AS first_seen_at,
    MAX(o.extracted_at) AS last_seen_at
  FROM unit_occurrences o
  GROUP BY o.unit_id
) src
WHERE src.unit_id = u.id;

-- ---------------------------------------------------------------------------
-- Atomic upsert RPC — one authoritative dedup decision for all write paths
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION upsert_canonical_unit(
  p_user_id UUID,
  p_statement TEXT,
  p_type TEXT,
  p_entities TEXT[] DEFAULT NULL,
  p_embedding vector(1536) DEFAULT NULL,
  p_embedding_model TEXT DEFAULT 'gemini-embedding-2-preview',
  p_source_url TEXT DEFAULT NULL,
  p_normalized_source_url TEXT DEFAULT NULL,
  p_source_domain TEXT DEFAULT NULL,
  p_source_title TEXT DEFAULT NULL,
  p_context_excerpt TEXT DEFAULT NULL,
  p_occurred_at DATE DEFAULT NULL,
  p_extracted_at TIMESTAMPTZ DEFAULT NOW(),
  p_source_type TEXT DEFAULT 'scout',
  p_content_sha256 TEXT DEFAULT NULL,
  p_statement_hash TEXT DEFAULT NULL,
  p_scout_id UUID DEFAULT NULL,
  p_scout_type TEXT DEFAULT NULL,
  p_scout_run_id UUID DEFAULT NULL,
  p_project_id UUID DEFAULT NULL,
  p_raw_capture_id UUID DEFAULT NULL,
  p_metadata JSONB DEFAULT '{}'::jsonb,
  p_semantic_threshold REAL DEFAULT 0.93,
  p_semantic_anchor_threshold REAL DEFAULT 0.88,
  p_semantic_limit INT DEFAULT 25
)
RETURNS TABLE (
  unit_id UUID,
  created_canonical BOOLEAN,
  merged_existing BOOLEAN,
  match_scope TEXT,
  occurrence_created BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_target_unit_id UUID;
  v_occurrence_id UUID;
  v_normalized_source_url TEXT;
  v_source_domain TEXT;
  v_entities TEXT[];
  v_existing_source BOOLEAN := FALSE;
BEGIN
  IF p_user_id IS NULL THEN
    RAISE EXCEPTION 'p_user_id is required';
  END IF;
  IF p_statement IS NULL OR btrim(p_statement) = '' THEN
    RAISE EXCEPTION 'p_statement is required';
  END IF;
  IF p_statement_hash IS NULL OR btrim(p_statement_hash) = '' THEN
    RAISE EXCEPTION 'p_statement_hash is required';
  END IF;
  IF p_type NOT IN ('fact', 'event', 'entity_update', 'promise') THEN
    RAISE EXCEPTION 'invalid unit type: %', p_type;
  END IF;
  IF p_source_type NOT IN ('scout', 'manual_ingest', 'agent_ingest', 'civic_promise') THEN
    RAISE EXCEPTION 'invalid source type: %', p_source_type;
  END IF;

  v_normalized_source_url := COALESCE(
    NULLIF(btrim(p_normalized_source_url), ''),
    normalize_source_url(p_source_url)
  );
  v_source_domain := NULLIF(btrim(p_source_domain), '');
  v_entities := text_array_union(NULL, p_entities);

  PERFORM pg_advisory_xact_lock(
    hashtextextended(p_user_id::TEXT || ':' || p_statement_hash, 0)
  );

  -- 1. Cheap same-scout exact checks.
  IF p_scout_id IS NOT NULL THEN
    IF v_target_unit_id IS NULL AND v_normalized_source_url IS NOT NULL THEN
      SELECT o.unit_id
      INTO v_target_unit_id
      FROM unit_occurrences o
      WHERE o.user_id = p_user_id
        AND o.scout_id = p_scout_id
        AND o.normalized_source_url = v_normalized_source_url
      ORDER BY o.extracted_at DESC
      LIMIT 1;
    END IF;

    IF v_target_unit_id IS NULL AND p_content_sha256 IS NOT NULL THEN
      SELECT o.unit_id
      INTO v_target_unit_id
      FROM unit_occurrences o
      WHERE o.user_id = p_user_id
        AND o.scout_id = p_scout_id
        AND o.content_sha256 = p_content_sha256
      ORDER BY o.extracted_at DESC
      LIMIT 1;
    END IF;

    IF v_target_unit_id IS NULL THEN
      SELECT o.unit_id
      INTO v_target_unit_id
      FROM unit_occurrences o
      WHERE o.user_id = p_user_id
        AND o.scout_id = p_scout_id
        AND o.statement_hash = p_statement_hash
      ORDER BY o.extracted_at DESC
      LIMIT 1;
    END IF;

    IF v_target_unit_id IS NOT NULL THEN
      match_scope := 'same_scout';
    END IF;
  END IF;

  -- 2. Cross-scout exact checks across the caller's corpus.
  IF v_target_unit_id IS NULL AND v_normalized_source_url IS NOT NULL THEN
    SELECT o.unit_id
    INTO v_target_unit_id
    FROM unit_occurrences o
    WHERE o.user_id = p_user_id
      AND o.normalized_source_url = v_normalized_source_url
    ORDER BY o.extracted_at DESC
    LIMIT 1;

    IF v_target_unit_id IS NOT NULL THEN
      match_scope := 'cross_scout_exact';
    END IF;
  END IF;

  IF v_target_unit_id IS NULL AND p_content_sha256 IS NOT NULL THEN
    SELECT o.unit_id
    INTO v_target_unit_id
    FROM unit_occurrences o
    WHERE o.user_id = p_user_id
      AND o.content_sha256 = p_content_sha256
    ORDER BY o.extracted_at DESC
    LIMIT 1;

    IF v_target_unit_id IS NOT NULL THEN
      match_scope := 'cross_scout_exact';
    END IF;
  END IF;

  IF v_target_unit_id IS NULL THEN
    SELECT o.unit_id
    INTO v_target_unit_id
    FROM unit_occurrences o
    WHERE o.user_id = p_user_id
      AND o.statement_hash = p_statement_hash
    ORDER BY o.extracted_at DESC
    LIMIT 1;

    IF v_target_unit_id IS NOT NULL THEN
      match_scope := 'cross_scout_exact';
    END IF;
  END IF;

  -- 3. Semantic match against canonical rows only.
  IF v_target_unit_id IS NULL AND p_embedding IS NOT NULL THEN
    SELECT candidate.id
    INTO v_target_unit_id
    FROM (
      SELECT
        u.id,
        u.source_domain,
        u.occurred_at,
        u.entities,
        (1 - (u.embedding <=> p_embedding))::REAL AS similarity
      FROM information_units u
      WHERE u.user_id = p_user_id
        AND u.embedding IS NOT NULL
      ORDER BY u.embedding <=> p_embedding
      LIMIT GREATEST(p_semantic_limit, 1)
    ) AS candidate
    WHERE candidate.similarity >= p_semantic_threshold
      OR (
        candidate.similarity >= p_semantic_anchor_threshold
        AND (
          (v_source_domain IS NOT NULL AND candidate.source_domain = v_source_domain)
          OR (
            p_occurred_at IS NOT NULL
            AND candidate.occurred_at IS NOT NULL
            AND abs(candidate.occurred_at - p_occurred_at) <= 7
          )
          OR (
            COALESCE(candidate.entities, ARRAY[]::TEXT[]) &&
            COALESCE(v_entities, ARRAY[]::TEXT[])
          )
        )
      )
    ORDER BY candidate.similarity DESC
    LIMIT 1;

    IF v_target_unit_id IS NOT NULL THEN
      match_scope := 'cross_scout_semantic';
    END IF;
  END IF;

  -- 4. Create a canonical row when nothing matched.
  IF v_target_unit_id IS NULL THEN
    INSERT INTO information_units (
      user_id,
      scout_id,
      scout_type,
      statement,
      type,
      entities,
      embedding,
      source_url,
      source_domain,
      source_title,
      occurred_at,
      project_id,
      used_in_article,
      extracted_at,
      context_excerpt,
      source_type,
      raw_capture_id,
      embedding_model,
      first_seen_at,
      last_seen_at,
      occurrence_count,
      source_count
    )
    VALUES (
      p_user_id,
      p_scout_id,
      p_scout_type,
      p_statement,
      p_type,
      v_entities,
      p_embedding,
      p_source_url,
      v_source_domain,
      p_source_title,
      p_occurred_at,
      p_project_id,
      FALSE,
      COALESCE(p_extracted_at, NOW()),
      p_context_excerpt,
      p_source_type,
      p_raw_capture_id,
      COALESCE(p_embedding_model, 'gemini-embedding-2-preview'),
      COALESCE(p_extracted_at, NOW()),
      COALESCE(p_extracted_at, NOW()),
      1,
      1
    )
    RETURNING id INTO v_target_unit_id;

    created_canonical := TRUE;
    merged_existing := FALSE;
    match_scope := 'new';
  ELSE
    created_canonical := FALSE;
    merged_existing := TRUE;

    SELECT EXISTS (
      SELECT 1
      FROM unit_occurrences o
      WHERE o.unit_id = v_target_unit_id
        AND (
          (v_normalized_source_url IS NOT NULL AND o.normalized_source_url = v_normalized_source_url)
          OR (
            v_normalized_source_url IS NULL
            AND p_content_sha256 IS NOT NULL
            AND o.content_sha256 = p_content_sha256
          )
        )
    )
    INTO v_existing_source;
  END IF;

  -- 5. Attach provenance. Within-run dedup in callers should make this cheap,
  --    but ON CONFLICT keeps replays idempotent.
  INSERT INTO unit_occurrences (
    unit_id,
    user_id,
    project_id,
    scout_id,
    scout_run_id,
    raw_capture_id,
    scout_type,
    source_kind,
    source_url,
    normalized_source_url,
    source_title,
    source_domain,
    content_sha256,
    statement_hash,
    occurred_at,
    extracted_at,
    metadata
  )
  VALUES (
    v_target_unit_id,
    p_user_id,
    p_project_id,
    p_scout_id,
    p_scout_run_id,
    p_raw_capture_id,
    p_scout_type,
    p_source_type,
    p_source_url,
    v_normalized_source_url,
    p_source_title,
    v_source_domain,
    p_content_sha256,
    p_statement_hash,
    p_occurred_at,
    COALESCE(p_extracted_at, NOW()),
    COALESCE(p_metadata, '{}'::jsonb)
  )
  ON CONFLICT DO NOTHING
  RETURNING id INTO v_occurrence_id;

  occurrence_created := v_occurrence_id IS NOT NULL;

  -- 6. Roll forward canonical counters + fill missing context only when a new
  --    occurrence actually landed.
  IF NOT created_canonical AND occurrence_created THEN
    UPDATE information_units
    SET
      last_seen_at = GREATEST(COALESCE(last_seen_at, p_extracted_at, NOW()), COALESCE(p_extracted_at, NOW())),
      occurrence_count = COALESCE(occurrence_count, 1) + 1,
      source_count = COALESCE(source_count, 1) + CASE WHEN v_existing_source THEN 0 ELSE 1 END,
      type = canonical_unit_type(type, p_type),
      entities = text_array_union(entities, v_entities),
      occurred_at = COALESCE(occurred_at, p_occurred_at),
      context_excerpt = COALESCE(NULLIF(context_excerpt, ''), NULLIF(p_context_excerpt, '')),
      source_url = COALESCE(NULLIF(source_url, ''), NULLIF(p_source_url, '')),
      source_title = COALESCE(NULLIF(source_title, ''), NULLIF(p_source_title, '')),
      source_domain = COALESCE(NULLIF(source_domain, ''), v_source_domain),
      scout_id = COALESCE(scout_id, p_scout_id),
      scout_type = COALESCE(scout_type, p_scout_type),
      project_id = COALESCE(project_id, p_project_id),
      raw_capture_id = COALESCE(raw_capture_id, p_raw_capture_id),
      source_type = COALESCE(NULLIF(source_type, ''), p_source_type),
      embedding = COALESCE(embedding, p_embedding),
      embedding_model = CASE
        WHEN embedding IS NULL AND p_embedding IS NOT NULL
          THEN COALESCE(p_embedding_model, embedding_model)
        ELSE embedding_model
      END
    WHERE id = v_target_unit_id;
  END IF;

  unit_id := v_target_unit_id;
  RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- Search RPC — project scope now derives from occurrences, not origin row
-- ---------------------------------------------------------------------------

DROP FUNCTION IF EXISTS semantic_search_units(vector, uuid, uuid, int, text, int);

CREATE OR REPLACE FUNCTION semantic_search_units(
  p_embedding  vector(1536) DEFAULT NULL,
  p_user_id    UUID         DEFAULT NULL,
  p_project_id UUID         DEFAULT NULL,
  p_limit      INT          DEFAULT 20,
  p_query_text TEXT         DEFAULT NULL,
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
        p_project_id IS NULL
        OR EXISTS (
          SELECT 1
          FROM unit_occurrences o
          WHERE o.unit_id = u.id
            AND o.user_id = p_user_id
            AND o.project_id = p_project_id
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
      ) AS rank_ix
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
        COALESCE(1.0 / (p_rrf_k + s.rank_ix), 0.0) AS rrf_score
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
    m.rrf_score::REAL AS similarity
  FROM merged m
  JOIN scoped_units u ON u.id = m.id
  ORDER BY m.rrf_score DESC
  LIMIT p_limit;
$$;
