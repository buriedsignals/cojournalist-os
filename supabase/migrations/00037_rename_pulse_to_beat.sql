-- 00037_rename_pulse_to_beat.sql
-- Canonical scout type rename: pulse -> beat.
--
-- Forward-only migration. Rewrites stored scout-type values, updates the live
-- scouts type constraint, and aligns credit/audit terminology so all current
-- contracts use `beat`.

BEGIN;

ALTER TABLE scouts
DROP CONSTRAINT IF EXISTS scouts_type_check;

UPDATE scouts
SET type = 'beat'
WHERE type = 'pulse';

UPDATE execution_records
SET scout_type = 'beat'
WHERE scout_type = 'pulse';

UPDATE information_units
SET scout_type = 'beat'
WHERE scout_type = 'pulse';

UPDATE usage_records
SET scout_type = 'beat'
WHERE scout_type = 'pulse';

UPDATE usage_records
SET operation = 'beat'
WHERE operation = 'pulse';

ALTER TABLE scouts
ADD CONSTRAINT scouts_type_check
CHECK (type = ANY (ARRAY['web'::text, 'beat'::text, 'social'::text, 'civic'::text]));

COMMIT;
