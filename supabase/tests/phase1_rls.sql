BEGIN;
SELECT plan(9);

SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'projects'),
  'RLS must be enabled on projects');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'project_members'),
  'RLS must be enabled on project_members');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'raw_captures'),
  'RLS must be enabled on raw_captures');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'ingests'),
  'RLS must be enabled on ingests');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'civic_extraction_queue'),
  'RLS must be enabled on civic_extraction_queue');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'apify_run_queue'),
  'RLS must be enabled on apify_run_queue');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'entities'),
  'RLS must be enabled on entities');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'unit_entities'),
  'RLS must be enabled on unit_entities');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE relname = 'reflections'),
  'RLS must be enabled on reflections');

SELECT * FROM finish();
ROLLBACK;
