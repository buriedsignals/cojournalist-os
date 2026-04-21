-- 00010_phase1_indexes.sql
-- Indexes for Phase 1 tables and new columns.
-- B-tree, HNSW (vector), trigram GIN, array GIN, and partial indexes.

-- information_units filtering
CREATE INDEX idx_units_project ON information_units (project_id, extracted_at DESC);
CREATE INDEX idx_units_occurred ON information_units (user_id, occurred_at DESC NULLS LAST);
CREATE INDEX idx_units_unused ON information_units (user_id, used_in_article, extracted_at DESC)
  WHERE used_in_article = FALSE;

-- raw_captures
CREATE INDEX idx_raw_run ON raw_captures (scout_run_id);
CREATE INDEX idx_raw_user_time ON raw_captures (user_id, captured_at DESC);
CREATE INDEX idx_raw_hash ON raw_captures (content_sha256);
CREATE INDEX idx_raw_expires ON raw_captures (expires_at) WHERE expires_at IS NOT NULL;

-- ingests
CREATE INDEX idx_ingests_user ON ingests (user_id, created_at DESC);

-- entities
CREATE INDEX idx_entities_user_type ON entities (user_id, type);
CREATE INDEX idx_entities_canonical_trgm ON entities USING gin (canonical_name gin_trgm_ops);
CREATE INDEX idx_entities_aliases_gin ON entities USING gin (aliases);
CREATE INDEX idx_entities_embedding ON entities
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- unit_entities junction
CREATE INDEX idx_ue_entity ON unit_entities (entity_id);
CREATE INDEX idx_ue_user ON unit_entities (user_id);
CREATE INDEX idx_ue_unresolved ON unit_entities (user_id)
  WHERE entity_id IS NULL;

-- reflections
CREATE INDEX idx_reflections_user ON reflections (user_id, created_at DESC);
CREATE INDEX idx_reflections_project ON reflections (project_id, created_at DESC);
CREATE INDEX idx_reflections_timerange ON reflections (user_id, time_range_start, time_range_end);
CREATE INDEX idx_reflections_embedding ON reflections
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- scout project linkage
CREATE INDEX idx_scouts_project ON scouts (project_id);

-- queue workers (partial indexes for efficient pending lookup)
CREATE INDEX idx_civic_queue_work ON civic_extraction_queue (status, created_at)
  WHERE status IN ('pending','processing');
CREATE INDEX idx_apify_queue_run_id ON apify_run_queue (apify_run_id)
  WHERE apify_run_id IS NOT NULL;
CREATE INDEX idx_apify_queue_pending ON apify_run_queue (status, started_at)
  WHERE status IN ('pending','running');
