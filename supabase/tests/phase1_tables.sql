BEGIN;
SELECT plan(9);

SELECT has_table('public', 'projects', 'projects table must exist');
SELECT has_table('public', 'project_members', 'project_members table must exist');
SELECT has_table('public', 'raw_captures', 'raw_captures table must exist');
SELECT has_table('public', 'ingests', 'ingests table must exist');
SELECT has_table('public', 'civic_extraction_queue', 'civic_extraction_queue table must exist');
SELECT has_table('public', 'apify_run_queue', 'apify_run_queue table must exist');
SELECT has_table('public', 'entities', 'entities table must exist');
SELECT has_table('public', 'unit_entities', 'unit_entities table must exist');
SELECT has_table('public', 'reflections', 'reflections table must exist');

SELECT * FROM finish();
ROLLBACK;
