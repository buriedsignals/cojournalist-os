-- 00040_execution_embedding_model.sql
-- Track execution-record embedding versions so Gemini Embedding 2 prefix
-- migrations can be audited and backfilled safely.

ALTER TABLE execution_records
  ADD COLUMN IF NOT EXISTS embedding_model TEXT NOT NULL DEFAULT 'gemini-embedding-2-preview';
