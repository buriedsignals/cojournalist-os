-- 00035_refund_credits_rpc.sql
-- Atomic undo for a single decrement_credits call. Used by scout workers on
-- error paths (Firecrawl 502, empty markdown, extraction failure) so users
-- don't pay for scheduled runs that never produced billable output.
--
-- Mirrors decrement_credits semantics: respects active_org_id (team pool
-- first, else user pool) and caps the refund at monthly_cap to avoid
-- accidentally inflating a balance past its MuckRock-issued ceiling.
-- Also writes a negative-cost usage_records row so the admin dashboard
-- still reflects an audit trail (the net of debit + refund is 0).
--
-- Returns `new_balance` (not `balance`) to avoid the OUT-parameter/column
-- name clash that breaks UPDATE ... SET balance = LEAST(balance + p_cost, ...).

DROP FUNCTION IF EXISTS refund_credits(UUID, INT, UUID, TEXT, TEXT);

CREATE OR REPLACE FUNCTION refund_credits(
    p_user_id    UUID,
    p_cost       INT,
    p_scout_id   UUID,
    p_scout_type TEXT,
    p_operation  TEXT
)
RETURNS TABLE (new_balance INT, owner TEXT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_org UUID;
    v_new INT;
    v_owner TEXT;
BEGIN
    SELECT active_org_id INTO v_org FROM user_preferences WHERE user_id = p_user_id;

    IF v_org IS NOT NULL THEN
        UPDATE credit_accounts ca
           SET balance = LEAST(ca.balance + p_cost, ca.monthly_cap),
               updated_at = NOW()
         WHERE ca.org_id = v_org
         RETURNING ca.balance INTO v_new;
        IF v_new IS NOT NULL THEN v_owner := 'org'; END IF;
    END IF;

    IF v_new IS NULL THEN
        UPDATE credit_accounts ca
           SET balance = LEAST(ca.balance + p_cost, ca.monthly_cap),
               updated_at = NOW()
         WHERE ca.user_id = p_user_id
         RETURNING ca.balance INTO v_new;
        v_owner := 'user';
    END IF;

    IF v_new IS NULL THEN
        -- Nothing to refund into. Silently no-op rather than raising — the
        -- caller's error path already handles the primary failure.
        RETURN;
    END IF;

    INSERT INTO usage_records(user_id, org_id, scout_id, scout_type, operation, cost)
    VALUES (
        p_user_id,
        CASE WHEN v_owner = 'org' THEN v_org END,
        p_scout_id,
        p_scout_type,
        p_operation || ':refund',
        -p_cost
    );

    new_balance := v_new;
    owner := v_owner;
    RETURN NEXT;
END;
$$;

REVOKE EXECUTE ON FUNCTION refund_credits FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION refund_credits TO service_role;

COMMENT ON FUNCTION refund_credits IS
  'Undoes a prior decrement_credits call on scout-worker error paths. '
  'Caps refunds at monthly_cap and writes a negative-cost usage_records row.';
