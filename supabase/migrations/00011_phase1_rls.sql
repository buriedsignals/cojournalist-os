-- 00011_phase1_rls.sql
-- Enable RLS on Phase 1 tables; add team-visibility SELECT policies to information_units + scouts.
-- The FastAPI / Edge Function backend connects via service role which bypasses RLS.
-- These policies protect data when accessed directly via PostgREST / Supabase client.

-- Enable RLS on all new tables
ALTER TABLE projects              ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_members       ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_captures          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingests               ENABLE ROW LEVEL SECURITY;
ALTER TABLE civic_extraction_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE apify_run_queue       ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities              ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_entities         ENABLE ROW LEVEL SECURITY;
ALTER TABLE reflections           ENABLE ROW LEVEL SECURITY;

-- projects: read if owner OR team member
CREATE POLICY projects_read ON projects FOR SELECT USING (
  (SELECT auth.uid()) = user_id
  OR EXISTS (
    SELECT 1 FROM project_members m
    WHERE m.project_id = projects.id
      AND m.user_id = (SELECT auth.uid())
  )
);
CREATE POLICY projects_write ON projects FOR ALL
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);

-- project_members: members see their own membership rows directly.
-- Breaking the reference to projects here avoids the policies_read<->pm_all
-- recursion that Postgres detects on the first mutual query. Admin/owner
-- queries that need all members of a project must use the service role.
CREATE POLICY pm_self ON project_members FOR ALL USING (
  (SELECT auth.uid()) = user_id
);

-- raw_captures, ingests, queues: owner-only (simple pattern)
CREATE POLICY raw_user   ON raw_captures          FOR ALL USING ((SELECT auth.uid()) = user_id);
CREATE POLICY ing_user   ON ingests               FOR ALL USING ((SELECT auth.uid()) = user_id);
CREATE POLICY civq_user  ON civic_extraction_queue FOR ALL USING ((SELECT auth.uid()) = user_id);
CREATE POLICY apq_user   ON apify_run_queue       FOR ALL USING ((SELECT auth.uid()) = user_id);

-- entities, unit_entities: owner-only
CREATE POLICY ent_user   ON entities              FOR ALL USING ((SELECT auth.uid()) = user_id);
CREATE POLICY ue_user    ON unit_entities         FOR ALL USING ((SELECT auth.uid()) = user_id);

-- reflections: read if owner OR project is shared via team
CREATE POLICY refl_read ON reflections FOR SELECT USING (
  (SELECT auth.uid()) = user_id
  OR (project_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM project_members m
    WHERE m.project_id = reflections.project_id
      AND m.user_id = (SELECT auth.uid())
  ))
);
CREATE POLICY refl_write ON reflections FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY refl_update ON reflections FOR UPDATE USING ((SELECT auth.uid()) = user_id);
CREATE POLICY refl_delete ON reflections FOR DELETE USING ((SELECT auth.uid()) = user_id);

-- Existing tables: replace single ALL policy with granular read + owner-only write
DROP POLICY IF EXISTS units_user ON information_units;
CREATE POLICY units_read ON information_units FOR SELECT USING (
  (SELECT auth.uid()) = user_id
  OR (project_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM project_members m
    WHERE m.project_id = information_units.project_id
      AND m.user_id = (SELECT auth.uid())
  ))
);
CREATE POLICY units_insert ON information_units FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY units_update ON information_units FOR UPDATE USING ((SELECT auth.uid()) = user_id);
CREATE POLICY units_delete ON information_units FOR DELETE USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS scouts_user ON scouts;
CREATE POLICY scouts_read ON scouts FOR SELECT USING (
  (SELECT auth.uid()) = user_id
  OR (project_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM project_members m
    WHERE m.project_id = scouts.project_id
      AND m.user_id = (SELECT auth.uid())
  ))
);
CREATE POLICY scouts_insert ON scouts FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY scouts_update ON scouts FOR UPDATE USING ((SELECT auth.uid()) = user_id);
CREATE POLICY scouts_delete ON scouts FOR DELETE USING ((SELECT auth.uid()) = user_id);
