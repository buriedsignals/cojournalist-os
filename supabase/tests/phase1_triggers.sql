BEGIN;
SELECT plan(3);

SELECT has_trigger('public', 'projects', 'projects_updated_at', '');
SELECT has_trigger('public', 'entities', 'entities_updated_at', '');
SELECT has_trigger('public', 'civic_extraction_queue', 'civic_queue_updated_at', '');

SELECT * FROM finish();
ROLLBACK;
