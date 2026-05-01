-- Repair baseline timestamps for legacy scouts that already have baseline
-- evidence from successful runs or social snapshots. First-run guards
-- still apply to scouts with no repair source.

UPDATE scouts s
SET baseline_established_at = latest_success.completed_at,
    updated_at = NOW()
FROM (
    SELECT DISTINCT ON (scout_id)
        scout_id,
        COALESCE(completed_at, started_at) AS completed_at
    FROM scout_runs
    WHERE status = 'success'
      AND (completed_at IS NOT NULL OR started_at IS NOT NULL)
    ORDER BY scout_id, completed_at DESC NULLS LAST, started_at DESC
) AS latest_success
WHERE s.id = latest_success.scout_id
  AND s.type = 'beat'
  AND s.baseline_established_at IS NULL;

UPDATE scouts s
SET baseline_established_at = COALESCE(ps.updated_at, NOW()),
    updated_at = NOW()
FROM post_snapshots ps
WHERE s.id = ps.scout_id
  AND s.type = 'social'
  AND s.baseline_established_at IS NULL;
