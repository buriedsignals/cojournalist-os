-- 00005_triggers.sql
-- Automatic updated_at trigger for tables that track modification time.

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_scouts_updated_at
    BEFORE UPDATE ON scouts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_user_prefs_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_promises_updated_at
    BEFORE UPDATE ON promises
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
