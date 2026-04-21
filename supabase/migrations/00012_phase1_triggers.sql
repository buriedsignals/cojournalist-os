-- 00012_phase1_triggers.sql
-- updated_at triggers for Phase 1 tables that track modification time.
-- Reuses update_updated_at() function from 00005_triggers.sql.

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER entities_updated_at
  BEFORE UPDATE ON entities
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER civic_queue_updated_at
  BEFORE UPDATE ON civic_extraction_queue
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
