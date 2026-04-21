-- 00034_rls_hardening.sql
-- Hardens RLS posture flagged by the 2026-04-21 audit:
--   A.1 — civic_extraction_queue + apify_run_queue: add WITH CHECK that
--         asserts the caller owns both the row and the referenced scout, and
--         revoke INSERT/UPDATE/DELETE from authenticated/anon so only
--         service-role (workers, cron) can enqueue. Matches the "service-role
--         only by design" documentation.
--   A.3 — scout_runs / post_snapshots / seen_records / promises: same
--         user-JWT write revoke (these are worker-written in prod; no user
--         code writes them) + explicit WITH CHECK for completeness.
--   A.10 — Wrap bare `auth.uid()` in `(SELECT auth.uid())` on every policy
--         flagged by the rls_initplan linter. Folds the auth call into a
--         single InitPlan that runs once per query instead of once per row.

-- ---------------------------------------------------------------------------
-- A.1 + A.3 — queue tables + user-owned write tables
-- Service-role-only writes. SELECT remains open to the row owner via RLS.
-- ---------------------------------------------------------------------------

REVOKE INSERT, UPDATE, DELETE ON public.civic_extraction_queue FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.apify_run_queue       FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.scout_runs            FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.post_snapshots        FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.seen_records          FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.promises              FROM anon, authenticated;

-- Drop the old FOR ALL USING-only policies and replace with explicit
-- USING + WITH CHECK that also verifies scout ownership for queue rows.
DROP POLICY IF EXISTS civq_user ON public.civic_extraction_queue;
CREATE POLICY civq_user ON public.civic_extraction_queue
  FOR ALL
  USING (user_id = (SELECT auth.uid()))
  WITH CHECK (
    user_id = (SELECT auth.uid())
    AND EXISTS (
      SELECT 1 FROM public.scouts s
      WHERE s.id = scout_id AND s.user_id = (SELECT auth.uid())
    )
  );

DROP POLICY IF EXISTS apq_user ON public.apify_run_queue;
CREATE POLICY apq_user ON public.apify_run_queue
  FOR ALL
  USING (user_id = (SELECT auth.uid()))
  WITH CHECK (
    user_id = (SELECT auth.uid())
    AND EXISTS (
      SELECT 1 FROM public.scouts s
      WHERE s.id = scout_id AND s.user_id = (SELECT auth.uid())
    )
  );

-- ---------------------------------------------------------------------------
-- A.10 — wrap `auth.uid()` in `(SELECT auth.uid())` for initplan caching
-- ---------------------------------------------------------------------------

ALTER POLICY runs_user    ON public.scout_runs        USING ((SELECT auth.uid()) = user_id);
ALTER POLICY exec_user    ON public.execution_records USING ((SELECT auth.uid()) = user_id);
ALTER POLICY posts_user   ON public.post_snapshots    USING ((SELECT auth.uid()) = user_id);
ALTER POLICY seen_user    ON public.seen_records      USING ((SELECT auth.uid()) = user_id);
ALTER POLICY promises_user ON public.promises         USING ((SELECT auth.uid()) = user_id);
ALTER POLICY prefs_user   ON public.user_preferences  USING ((SELECT auth.uid()) = user_id);

-- MCP OAuth clients — same pattern
ALTER POLICY clients_owner_select ON public.mcp_oauth_clients
  USING ((SELECT auth.uid()) = user_id);

-- Org membership + credits + usage — these carry an inner subquery on
-- auth.uid() that the initplan advice matters most for (pro/team users
-- traverse these on every dashboard load).
ALTER POLICY org_members_read ON public.org_members
  USING (user_id = (SELECT auth.uid()));

ALTER POLICY orgs_read ON public.orgs
  USING (
    id IN (
      SELECT m.org_id FROM public.org_members m
      WHERE m.user_id = (SELECT auth.uid())
    )
  );

ALTER POLICY credit_accounts_read ON public.credit_accounts
  USING (
    user_id = (SELECT auth.uid())
    OR org_id IN (
      SELECT m.org_id FROM public.org_members m
      WHERE m.user_id = (SELECT auth.uid())
    )
  );

ALTER POLICY usage_records_read ON public.usage_records
  USING (
    user_id = (SELECT auth.uid())
    OR org_id IN (
      SELECT m.org_id FROM public.org_members m
      WHERE m.user_id = (SELECT auth.uid())
    )
  );
