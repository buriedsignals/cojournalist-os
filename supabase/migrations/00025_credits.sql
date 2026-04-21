-- 00025_credits.sql
-- Credit / entitlement system — replicates the DynamoDB shape from the source repo
-- (USER#/CREDITS, ORG#/CREDITS, ORG#/MEMBER#, USAGE#) in Postgres.
--
-- Design owner: MuckRock is the billing IdP. Tier + monthly_cap flow in via the
-- billing-webhook Edge Function. The user Edge Function reads these tables on
-- GET /me. Scout-execute Edge Functions call decrement_credits() before running.
--
-- Atomicity: DDB's ConditionExpression maps to Postgres
--   UPDATE ... WHERE balance >= cost RETURNING balance
-- The CHECK (balance >= 0) column constraint is belt-and-braces; any overdraft
-- aborts the transaction.

-- ============================================================
-- ORGS — MuckRock orgs (individual and team)
-- ============================================================
CREATE TABLE orgs (
    id UUID PRIMARY KEY,                             -- MuckRock org UUID, preserved
    name TEXT NOT NULL,
    is_individual BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE org_members (
    org_id UUID REFERENCES orgs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    tier_before_team TEXT CHECK (tier_before_team IN ('free', 'pro')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX idx_org_members_user ON org_members(user_id);

-- ============================================================
-- CREDIT_ACCOUNTS — polymorphic (user XOR org)
-- ============================================================
CREATE TABLE credit_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    org_id  UUID REFERENCES orgs(id)       ON DELETE CASCADE,
    tier TEXT NOT NULL CHECK (tier IN ('free', 'pro', 'team')),
    monthly_cap INT NOT NULL,
    balance INT NOT NULL CHECK (balance >= 0),       -- overdraft guard
    update_on DATE,                                   -- next reset date (from MuckRock entitlement)
    seated_count INT DEFAULT 0,                       -- team pool only
    entitlement_source TEXT,                          -- 'cojournalist-pro' | 'cojournalist-team' | NULL
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK ((user_id IS NULL) <> (org_id IS NULL)),   -- exactly one owner
    UNIQUE (user_id),
    UNIQUE (org_id)
);

-- ============================================================
-- USAGE_RECORDS — audit trail (90-day retention, matches DDB USAGE# TTL)
-- ============================================================
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    org_id UUID REFERENCES orgs(id),
    scout_id UUID,
    scout_type TEXT,
    operation TEXT NOT NULL,                          -- pricing key, e.g. "pulse", "civic"
    cost INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '90 days')
);

CREATE INDEX idx_usage_created ON usage_records(created_at);
CREATE INDEX idx_usage_user    ON usage_records(user_id, created_at DESC);
CREATE INDEX idx_usage_org     ON usage_records(org_id,  created_at DESC) WHERE org_id IS NOT NULL;
CREATE INDEX idx_usage_expires ON usage_records(expires_at);

-- ============================================================
-- user_preferences: denormalized tier + active_org_id pointer
-- Avoids a join on every request; webhook handler keeps these in sync.
-- ============================================================
ALTER TABLE user_preferences
    ADD COLUMN tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'team')),
    ADD COLUMN active_org_id UUID REFERENCES orgs(id);

-- ============================================================
-- decrement_credits() — atomic, transactional, writes audit row
-- Called by scout-execute Edge Functions via service_role.
-- Team path first (if active_org_id set); falls back to user pool on
-- ORG# gone / insufficient team credits (matches DDB lazy-invalidation).
-- ============================================================
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
        UPDATE credit_accounts
           SET balance = balance - p_cost, updated_at = NOW()
         WHERE org_id = v_org AND balance >= p_cost
         RETURNING credit_accounts.balance INTO v_new;

        IF v_new IS NOT NULL THEN
            v_owner := 'org';
        END IF;
    END IF;

    IF v_new IS NULL THEN
        UPDATE credit_accounts
           SET balance = balance - p_cost, updated_at = NOW()
         WHERE user_id = p_user_id AND balance >= p_cost
         RETURNING credit_accounts.balance INTO v_new;
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

-- ============================================================
-- topup_team_credits() — MuckRock webhook drives this on seat/plan change
-- Mirrors update_org_credits() in source backend/app/services/user_service.py.
-- Idempotent: retry with the same new_cap is a no-op.
-- ============================================================
CREATE OR REPLACE FUNCTION topup_team_credits(
    p_org_id UUID,
    p_new_cap INT,
    p_update_on DATE
)
RETURNS INT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_balance INT;
BEGIN
    UPDATE credit_accounts
       SET balance = balance + GREATEST(0, p_new_cap - monthly_cap),
           monthly_cap = p_new_cap,
           update_on = p_update_on,
           updated_at = NOW()
     WHERE org_id = p_org_id
     RETURNING credit_accounts.balance INTO v_balance;

    -- Downgrade: cap balance at new_cap
    UPDATE credit_accounts
       SET balance = p_new_cap
     WHERE org_id = p_org_id AND balance > p_new_cap
     RETURNING credit_accounts.balance INTO v_balance;

    RETURN v_balance;
END;
$$;

REVOKE EXECUTE ON FUNCTION topup_team_credits FROM PUBLIC, anon, authenticated;

-- ============================================================
-- reset_expired_credits() — called by cron daily; resets balance to monthly_cap
-- where update_on has passed. Mirrors MuckRock entitlement reset cadence.
-- ============================================================
CREATE OR REPLACE FUNCTION reset_expired_credits()
RETURNS INT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE credit_accounts
       SET balance = monthly_cap,
           update_on = update_on + INTERVAL '1 month',
           updated_at = NOW()
     WHERE update_on <= CURRENT_DATE;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

REVOKE EXECUTE ON FUNCTION reset_expired_credits FROM PUBLIC, anon, authenticated;

-- ============================================================
-- RLS — read own rows (user's own + their team's shared pool); no user writes.
-- Only service_role + SECURITY DEFINER RPCs can mutate.
-- ============================================================
ALTER TABLE orgs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_members     ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records   ENABLE ROW LEVEL SECURITY;

CREATE POLICY orgs_read ON orgs FOR SELECT USING (
    id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())
);

CREATE POLICY org_members_read ON org_members FOR SELECT USING (
    user_id = auth.uid()
);

CREATE POLICY credit_accounts_read ON credit_accounts FOR SELECT USING (
    user_id = auth.uid()
    OR org_id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())
);

CREATE POLICY usage_records_read ON usage_records FOR SELECT USING (
    user_id = auth.uid()
    OR org_id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())
);
