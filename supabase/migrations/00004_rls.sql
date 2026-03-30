-- 00004_rls.sql
-- Row Level Security policies.
-- The FastAPI backend connects via the Supabase service role key, which bypasses RLS.
-- These policies protect data when accessed via PostgREST / Supabase client directly.

ALTER TABLE scouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE scout_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE seen_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE information_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE promises ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- User-scoped access (PostgREST / Supabase client)
CREATE POLICY scouts_user ON scouts FOR ALL USING (auth.uid() = user_id);
CREATE POLICY runs_user ON scout_runs FOR ALL USING (auth.uid() = user_id);
CREATE POLICY exec_user ON execution_records FOR ALL USING (auth.uid() = user_id);
CREATE POLICY posts_user ON post_snapshots FOR ALL USING (auth.uid() = user_id);
CREATE POLICY seen_user ON seen_records FOR ALL USING (auth.uid() = user_id);
CREATE POLICY units_user ON information_units FOR ALL USING (auth.uid() = user_id);
CREATE POLICY promises_user ON promises FOR ALL USING (auth.uid() = user_id);
CREATE POLICY prefs_user ON user_preferences FOR ALL USING (auth.uid() = user_id);
