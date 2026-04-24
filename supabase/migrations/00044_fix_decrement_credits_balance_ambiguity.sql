-- 00044_fix_decrement_credits_balance_ambiguity.sql
-- Local Postgres can treat the RETURNS TABLE(balance, owner) OUT parameter
-- as ambiguous against credit_accounts.balance inside the UPDATE statement.
-- Qualify the table references so scheduled scout decrements work reliably.

CREATE OR REPLACE FUNCTION decrement_credits(
    p_user_id UUID,
    p_cost INT,
    p_scout_id UUID,
    p_scout_type TEXT,
    p_operation TEXT
)
RETURNS TABLE(balance INT, owner TEXT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_org UUID;
    v_new INT;
    v_owner TEXT;
BEGIN
    SELECT active_org_id INTO v_org FROM user_preferences WHERE user_id = p_user_id;

    IF v_org IS NOT NULL THEN
        UPDATE credit_accounts AS ca
           SET balance = ca.balance - p_cost,
               updated_at = NOW()
         WHERE ca.org_id = v_org
           AND ca.balance >= p_cost
         RETURNING ca.balance INTO v_new;

        IF v_new IS NOT NULL THEN
            v_owner := 'org';
        END IF;
    END IF;

    IF v_new IS NULL THEN
        UPDATE credit_accounts AS ca
           SET balance = ca.balance - p_cost,
               updated_at = NOW()
         WHERE ca.user_id = p_user_id
           AND ca.balance >= p_cost
         RETURNING ca.balance INTO v_new;
        v_owner := 'user';
    END IF;

    IF v_new IS NULL THEN
        RAISE EXCEPTION 'insufficient_credits' USING ERRCODE = 'P0002';
    END IF;

    INSERT INTO usage_records(user_id, org_id, scout_id, scout_type, operation, cost)
    VALUES (
        p_user_id,
        CASE WHEN v_owner = 'org' THEN v_org END,
        p_scout_id,
        p_scout_type,
        p_operation,
        p_cost
    );

    RETURN QUERY SELECT v_new, v_owner;
END;
$$;

REVOKE EXECUTE ON FUNCTION decrement_credits FROM PUBLIC, anon, authenticated;
