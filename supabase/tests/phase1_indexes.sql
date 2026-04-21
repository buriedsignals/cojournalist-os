BEGIN;
SELECT plan(14);

-- B-tree filtering indexes on information_units
SELECT has_index('public', 'information_units', 'idx_units_project',
  '(project_id, extracted_at DESC)');
SELECT has_index('public', 'information_units', 'idx_units_occurred', '');
SELECT has_index('public', 'information_units', 'idx_units_unused', '');

-- Raw captures
SELECT has_index('public', 'raw_captures', 'idx_raw_run', '');
SELECT has_index('public', 'raw_captures', 'idx_raw_user_time', '');
SELECT has_index('public', 'raw_captures', 'idx_raw_hash', '');
SELECT has_index('public', 'raw_captures', 'idx_raw_expires', '');

-- Entities
SELECT has_index('public', 'entities', 'idx_entities_user_type', '');
SELECT has_index('public', 'entities', 'idx_entities_embedding', 'HNSW vector index');
SELECT has_index('public', 'unit_entities', 'idx_ue_entity', '');
SELECT has_index('public', 'unit_entities', 'idx_ue_unresolved', 'partial index for unresolved mentions');

-- Reflections
SELECT has_index('public', 'reflections', 'idx_reflections_embedding', 'HNSW vector index');
SELECT has_index('public', 'reflections', 'idx_reflections_timerange', '');

-- Queues
SELECT has_index('public', 'civic_extraction_queue', 'idx_civic_queue_work',
  'partial index for pending/processing items');

SELECT * FROM finish();
ROLLBACK;
