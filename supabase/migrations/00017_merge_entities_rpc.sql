-- 00017_merge_entities_rpc.sql
-- Merge one or more duplicate entities into a canonical one.
-- Unions aliases, remaps unit_entities, recomputes mention_count, deletes
-- the merged rows. SECURITY DEFINER + explicit ownership check since the
-- function bypasses RLS.

CREATE OR REPLACE FUNCTION merge_entities(
  p_user_id    UUID,
  p_keep_id    UUID,
  p_merge_ids  UUID[]
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  -- Ownership: keeper must belong to caller
  IF NOT EXISTS (SELECT 1 FROM entities WHERE id = p_keep_id AND user_id = p_user_id) THEN
    RAISE EXCEPTION 'merge_entities: keeper % not owned by caller', p_keep_id;
  END IF;

  -- Ownership: every merge source must also belong to caller
  IF EXISTS (
    SELECT 1 FROM entities
    WHERE id = ANY(p_merge_ids) AND user_id <> p_user_id
  ) THEN
    RAISE EXCEPTION 'merge_entities: one or more merge sources not owned by caller';
  END IF;

  -- Union aliases: keeper aliases + each merged entity's canonical_name + aliases
  UPDATE entities k
  SET aliases = ARRAY(
    SELECT DISTINCT a FROM (
      SELECT unnest(k.aliases) AS a
      UNION ALL
      SELECT m.canonical_name FROM entities m WHERE m.id = ANY(p_merge_ids)
      UNION ALL
      SELECT unnest(m.aliases) FROM entities m WHERE m.id = ANY(p_merge_ids)
    ) s
    WHERE a IS NOT NULL AND a <> ''
  )
  WHERE k.id = p_keep_id;

  -- Remap junction rows; skip rows that would collide with existing mentions
  -- on the keeper (primary key is unit_id + mention_text).
  UPDATE unit_entities ue
  SET entity_id = p_keep_id,
      resolved_at = COALESCE(ue.resolved_at, NOW())
  WHERE ue.entity_id = ANY(p_merge_ids)
    AND NOT EXISTS (
      SELECT 1 FROM unit_entities k
      WHERE k.unit_id = ue.unit_id
        AND k.mention_text = ue.mention_text
        AND k.entity_id = p_keep_id
    );

  -- Any junction rows that did collide are now redundant; drop them.
  DELETE FROM unit_entities
  WHERE entity_id = ANY(p_merge_ids);

  -- Recompute mention_count on the keeper
  UPDATE entities
  SET mention_count = (
    SELECT COUNT(*) FROM unit_entities WHERE entity_id = p_keep_id
  )
  WHERE id = p_keep_id;

  -- Delete the merged sources
  DELETE FROM entities WHERE id = ANY(p_merge_ids);
END; $$;
