BEGIN;
SELECT plan(2);

-- On a fresh DB with no users, backfill produces zero Inbox projects
SELECT is(
  (SELECT COUNT(*) FROM projects WHERE is_default = TRUE)::int, 0,
  'No Inbox projects on empty DB');

-- Sanity: no scouts without project_id linkage when scouts table is empty
SELECT is(
  (SELECT COUNT(*) FROM scouts WHERE project_id IS NULL)::int, 0,
  'No scouts missing project_id on empty DB');

SELECT * FROM finish();
ROLLBACK;
