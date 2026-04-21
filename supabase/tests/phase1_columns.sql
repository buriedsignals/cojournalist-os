BEGIN;
SELECT plan(12);

SELECT has_column('public', 'information_units', 'extracted_at',
  'information_units.extracted_at (renamed from created_at)');
SELECT hasnt_column('public', 'information_units', 'created_at',
  'information_units.created_at must be renamed away');
SELECT has_column('public', 'information_units', 'occurred_at',
  'information_units.occurred_at for event date (distinct from extracted_at)');
SELECT has_column('public', 'information_units', 'context_excerpt',
  'information_units.context_excerpt for surrounding source paragraph');
SELECT has_column('public', 'information_units', 'source_type',
  'information_units.source_type: scout / manual_ingest / agent_ingest');
SELECT has_column('public', 'information_units', 'verified',
  'verification status flag');
SELECT has_column('public', 'information_units', 'verification_notes', '');
SELECT has_column('public', 'information_units', 'verified_by', '');
SELECT has_column('public', 'information_units', 'used_at', '');
SELECT has_column('public', 'information_units', 'used_in_url', '');
SELECT has_column('public', 'information_units', 'project_id',
  'FK to projects(id) for grouping');
SELECT has_column('public', 'information_units', 'raw_capture_id',
  'FK to raw_captures(id)');

SELECT * FROM finish();
ROLLBACK;
