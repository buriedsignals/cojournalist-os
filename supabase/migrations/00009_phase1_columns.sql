-- 00009_phase1_columns.sql
-- Information units column rename + additions; scouts.project_id linkage.

-- Rename created_at -> extracted_at (semantic: when scout caught the unit)
ALTER TABLE information_units RENAME COLUMN created_at TO extracted_at;

-- Temporal: when the event actually happened (LLM-extracted, nullable)
ALTER TABLE information_units ADD COLUMN occurred_at DATE;

-- Source context for verification without re-fetching
ALTER TABLE information_units ADD COLUMN context_excerpt TEXT;

-- Distinguish automated scout vs human/agent ingests
ALTER TABLE information_units
  ADD COLUMN source_type TEXT NOT NULL DEFAULT 'scout'
  CHECK (source_type IN ('scout','manual_ingest','agent_ingest'));

-- Verification workflow fields
ALTER TABLE information_units ADD COLUMN verified BOOLEAN DEFAULT FALSE;
ALTER TABLE information_units ADD COLUMN verification_notes TEXT;
ALTER TABLE information_units ADD COLUMN verified_by TEXT;
ALTER TABLE information_units ADD COLUMN verified_at TIMESTAMPTZ;

-- Usage-in-article tracking
ALTER TABLE information_units ADD COLUMN used_at TIMESTAMPTZ;
ALTER TABLE information_units ADD COLUMN used_in_url TEXT;

-- Grouping + raw source pointer
ALTER TABLE information_units
  ADD COLUMN project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
ALTER TABLE information_units
  ADD COLUMN raw_capture_id UUID REFERENCES raw_captures(id) ON DELETE SET NULL;

-- Embedding model versioning (insurance for future model swaps)
ALTER TABLE information_units
  ADD COLUMN embedding_model TEXT NOT NULL DEFAULT 'gemini-embedding-2-preview';

-- Scout -> project linkage (backfilled in 00013_phase1_backfill)
ALTER TABLE scouts ADD COLUMN project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
