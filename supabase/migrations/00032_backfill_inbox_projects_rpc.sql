-- 00032_backfill_inbox_projects_rpc.sql
-- Re-creates the Inbox-project backfill as a callable RPC so the v1→v2 data
-- migration script (scripts/migrate/main.ts) can invoke it during cutover.
-- Mirrors 00013_phase1_backfill.sql but is idempotent and callable multiple
-- times. Feed UI queries filter by project_id IS NOT NULL, so any scout
-- landing with project_id NULL is orphaned from the Inbox view.
--
-- Promotes any pre-existing "Inbox" project with is_default=false (edge
-- case: a user manually created one before migration) so the link step
-- still finds it.

DROP FUNCTION IF EXISTS public.backfill_inbox_projects_and_link_scouts();

CREATE OR REPLACE FUNCTION public.backfill_inbox_projects_and_link_scouts()
RETURNS TABLE (
  inbox_projects_created INT,
  inbox_projects_promoted INT,
  scouts_linked INT,
  units_linked INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
  v_created INT := 0;
  v_promoted INT := 0;
  v_scouts INT := 0;
  v_units INT := 0;
BEGIN
  -- One "Inbox" default project per scout owner who has no Inbox yet.
  WITH inserted AS (
    INSERT INTO public.projects (user_id, name, is_default)
    SELECT DISTINCT s.user_id, 'Inbox', TRUE
    FROM public.scouts s
    ON CONFLICT (user_id, name) DO NOTHING
    RETURNING 1
  )
  SELECT count(*) INTO v_created FROM inserted;

  -- Promote any pre-existing Inbox that the unique constraint kept us from
  -- inserting. Without this the link step skips every user who manually
  -- created an Inbox before the migration.
  WITH promoted AS (
    UPDATE public.projects
       SET is_default = TRUE
     WHERE name = 'Inbox' AND is_default = FALSE
    RETURNING 1
  )
  SELECT count(*) INTO v_promoted FROM promoted;

  -- Attach orphan scouts to their owner's Inbox.
  WITH linked AS (
    UPDATE public.scouts s
    SET project_id = p.id
    FROM public.projects p
    WHERE p.user_id = s.user_id
      AND p.is_default = TRUE
      AND s.project_id IS NULL
    RETURNING 1
  )
  SELECT count(*) INTO v_scouts FROM linked;

  -- Cascade: any information_units with NULL project_id inherit from scout.
  WITH linked_units AS (
    UPDATE public.information_units u
    SET project_id = s.project_id
    FROM public.scouts s
    WHERE s.id = u.scout_id
      AND u.project_id IS NULL
      AND s.project_id IS NOT NULL
    RETURNING 1
  )
  SELECT count(*) INTO v_units FROM linked_units;

  RETURN QUERY SELECT v_created, v_promoted, v_scouts, v_units;
END;
$$;

COMMENT ON FUNCTION public.backfill_inbox_projects_and_link_scouts IS
  'Creates default Inbox project per scout owner and links orphan scouts/units. '
  'Idempotent — safe to re-run. Called by scripts/migrate/main.ts phase 8.';

-- Service role only — this is a migration-time RPC, not for end users.
REVOKE ALL ON FUNCTION public.backfill_inbox_projects_and_link_scouts FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.backfill_inbox_projects_and_link_scouts TO service_role;
