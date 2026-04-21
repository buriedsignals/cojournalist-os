-- 00008_phase1_tables.sql
-- Phase 1 new tables: projects, raw_captures, ingests, queues, entities, reflections.

-- projects
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('private','team')),
  tags TEXT[] DEFAULT '{}',
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, name)
);

-- project_members (dormant in OSS; populated only by SaaS team feature)
CREATE TABLE project_members (
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer','editor','owner')),
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, user_id)
);

-- ingests (declared before raw_captures so FK can be set)
CREATE TABLE ingests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  kind TEXT NOT NULL CHECK (kind IN ('url','pdf','text','file')),
  source_url TEXT,
  title TEXT,
  criteria TEXT,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','processing','success','error')),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- raw_captures
CREATE TABLE raw_captures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
  scout_run_id UUID REFERENCES scout_runs(id) ON DELETE CASCADE,
  ingest_id UUID REFERENCES ingests(id) ON DELETE CASCADE,
  source_url TEXT,
  source_domain TEXT,
  content_md TEXT,
  storage_path TEXT,
  content_sha256 TEXT,
  token_count INT,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

-- civic_extraction_queue
CREATE TABLE civic_extraction_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  scout_id UUID NOT NULL REFERENCES scouts(id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  doc_kind TEXT NOT NULL CHECK (doc_kind IN ('pdf','html')),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','processing','done','failed')),
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT,
  raw_capture_id UUID REFERENCES raw_captures(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- apify_run_queue
CREATE TABLE apify_run_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  scout_id UUID NOT NULL REFERENCES scouts(id) ON DELETE CASCADE,
  apify_run_id TEXT,
  platform TEXT NOT NULL,
  handle TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','running','succeeded','failed','timeout')),
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- entities (canonical entity store with aliases + embedding)
CREATE TABLE entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  canonical_name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('person','org','place','policy','event','document','other')),
  aliases TEXT[] NOT NULL DEFAULT '{}',
  metadata JSONB NOT NULL DEFAULT '{}',
  embedding vector(1536),
  embedding_model TEXT NOT NULL DEFAULT 'gemini-embedding-2-preview',
  mention_count INT NOT NULL DEFAULT 0,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, canonical_name, type)
);

-- unit_entities (junction: unresolved mentions keep entity_id = NULL)
CREATE TABLE unit_entities (
  unit_id UUID REFERENCES information_units(id) ON DELETE CASCADE,
  entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  mention_text TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
  resolved_at TIMESTAMPTZ,
  PRIMARY KEY (unit_id, mention_text)
);

-- reflections (agent-written synthesized summaries)
CREATE TABLE reflections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  scope_description TEXT NOT NULL,
  content TEXT NOT NULL,
  time_range_start TIMESTAMPTZ,
  time_range_end TIMESTAMPTZ,
  generated_by TEXT NOT NULL,
  source_unit_ids UUID[] NOT NULL DEFAULT '{}',
  source_entity_ids UUID[] NOT NULL DEFAULT '{}',
  embedding vector(1536),
  embedding_model TEXT NOT NULL DEFAULT 'gemini-embedding-2-preview',
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
