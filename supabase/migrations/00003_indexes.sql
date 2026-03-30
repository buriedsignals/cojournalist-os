-- 00003_indexes.sql
-- All indexes: lookup indexes, TTL cleanup indexes, and HNSW vector indexes.

-- Scout lookups
CREATE INDEX idx_scouts_user ON scouts(user_id);
CREATE INDEX idx_scouts_type ON scouts(user_id, type);
CREATE INDEX idx_scouts_active ON scouts(user_id) WHERE is_active = TRUE;

-- Run queries (time-ordered)
CREATE INDEX idx_runs_scout ON scout_runs(scout_id, started_at DESC);
CREATE INDEX idx_runs_user_time ON scout_runs(user_id, started_at DESC);

-- Execution record lookups
CREATE INDEX idx_exec_scout ON execution_records(scout_id, completed_at DESC);

-- Information unit lookups
CREATE INDEX idx_units_user ON information_units(user_id);
CREATE INDEX idx_units_scout ON information_units(scout_id, created_at DESC);
CREATE INDEX idx_units_location ON information_units(user_id, country, state, city);
CREATE INDEX idx_units_article ON information_units(article_id);

-- Seen record lookups
CREATE INDEX idx_seen_scout ON seen_records(scout_id);

-- Promise lookups
CREATE INDEX idx_promises_scout ON promises(scout_id, created_at DESC);
CREATE INDEX idx_promises_user ON promises(user_id);

-- TTL cleanup (partial indexes for efficient DELETE scans)
CREATE INDEX idx_runs_expires ON scout_runs(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_exec_expires ON execution_records(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_units_expires ON information_units(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_seen_expires ON seen_records(expires_at) WHERE expires_at IS NOT NULL;

-- Vector similarity (HNSW -- works at any data volume, no calibration needed)
CREATE INDEX idx_exec_embedding ON execution_records
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_unit_embedding ON information_units
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
