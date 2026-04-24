# Credits & entitlements

System that gates scout execution by monthly credit budgets. MuckRock is the authority on tier + entitlement; Supabase holds the working balance and decrements it atomically per run.

Spec source: `docs/muckrock/plans-and-entitlements.md` (tiers, costs) and `docs/muckrock/entitlements-team-design.md` (team pool logic). Schema: `supabase/migrations/00025_credits.sql` + `00026_credits_cron.sql`.

## Tiers

| Tier | Monthly credits | Source | Billing |
|---|---|---|---|
| `free` | 100 | default | $0 |
| `pro` | 1,000 | MuckRock entitlement `cojournalist-pro` | $10/mo |
| `team` | 5,000 shared (+1,000/seat) | MuckRock entitlement `cojournalist-team` on a team org | $50/mo base |

Credit caps read from `resources.monthly_credits` on each entitlement. Admin emails in `ADMIN_EMAILS` env var auto-upgrade to `pro` on login.

## Credit costs

Ported verbatim to `supabase/functions/_shared/credits.ts`.

| Operation | Cost |
|---|---|
| `website_extraction` (Page Scout) | 1 |
| `beat` (Smart / Beat Scout) | 7 |
| `social_monitoring_instagram` / `_x` / `_tiktok` | 2 |
| `social_monitoring_facebook` | 15 |
| `social_extraction`, `instagram_extraction`, `tiktok_extraction` | 2 |
| `facebook_extraction`, `instagram_comments_extraction` | 15 |
| `feed_export` | 1 |
| `civic` | 10 (refunded on no-op/error) |
| `civic_discover` | 10 |

On-demand search is free. Civic scouts are weekly/monthly only — daily cadence is rejected at scout-create time by the `scouts` Edge Function schema.

## Tables

### `orgs`
MuckRock org replica; the `id` is the MuckRock org UUID (preserved).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | = MuckRock org UUID |
| `name` | TEXT NOT NULL | |
| `is_individual` | BOOLEAN | `true` for personal orgs |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `org_members`
Team membership roster. Composite PK `(org_id, user_id)`.

| Column | Type | Notes |
|---|---|---|
| `org_id` | UUID → `orgs(id)` ON DELETE CASCADE | |
| `user_id` | UUID → `auth.users(id)` ON DELETE CASCADE | |
| `tier_before_team` | TEXT CHECK IN ('free','pro') | For revert on team cancel |
| `joined_at` | TIMESTAMPTZ | |

Index: `idx_org_members_user(user_id)`.

### `credit_accounts`
Polymorphic — exactly one of `user_id`/`org_id` is set.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` ON DELETE CASCADE | mutually exclusive with `org_id` |
| `org_id` | UUID → `orgs(id)` ON DELETE CASCADE | mutually exclusive with `user_id` |
| `tier` | TEXT CHECK IN ('free','pro','team') | |
| `monthly_cap` | INT NOT NULL | From MuckRock entitlement |
| `balance` | INT NOT NULL CHECK (≥ 0) | Postgres-level overdraft guard |
| `update_on` | DATE | Next MuckRock billing cycle reset |
| `seated_count` | INT DEFAULT 0 | Team pool only |
| `entitlement_source` | TEXT | `cojournalist-pro` / `cojournalist-team` / NULL |
| `updated_at` | TIMESTAMPTZ | |

Constraints:
- `CHECK ((user_id IS NULL) <> (org_id IS NULL))` — exactly one owner
- `UNIQUE (user_id)`, `UNIQUE (org_id)` — one account per owner

### `usage_records`
90-day audit trail, rolled up for admin reports.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` | Always set (who triggered the decrement) |
| `org_id` | UUID → `orgs(id)` | Set when a team pool paid |
| `scout_id` | UUID | Not FK'd — scouts may be deleted before the audit expires |
| `scout_type` | TEXT | `web`/`beat`/`social`/`civic` |
| `operation` | TEXT NOT NULL | `CREDIT_COSTS` key |
| `cost` | INT NOT NULL | |
| `created_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ DEFAULT (NOW() + 90d) | Driver for cleanup cron |

Indexes: `idx_usage_created(created_at)`, `idx_usage_user(user_id, created_at DESC)`, `idx_usage_org(org_id, created_at DESC) WHERE org_id IS NOT NULL`, `idx_usage_expires(expires_at)`.

### `user_preferences` (extended in 00025)

| Column added | Type | Notes |
|---|---|---|
| `tier` | TEXT NOT NULL DEFAULT 'free' CHECK IN ('free','pro','team') | Denormalized from current entitlement |
| `active_org_id` | UUID → `orgs(id)` | The team pool to decrement against, if any |

The denormalized pointer exists so `decrement_credits` doesn't need to join `org_members` on every call.

## RPCs

### `decrement_credits(p_user_id, p_cost, p_scout_id, p_scout_type, p_operation) RETURNS TABLE(balance INT, owner TEXT)`

Atomic, transactional. Used by every scout-execute Edge Function before doing billable work.

**Flow**:
1. Read `user_preferences.active_org_id`.
2. If set, try `UPDATE credit_accounts SET balance = balance - cost WHERE org_id = :v_org AND balance >= cost RETURNING balance`. On hit, `owner = 'org'`.
3. Else fall back to `UPDATE ... WHERE user_id = :p_user_id AND balance >= cost`. On hit, `owner = 'user'`.
4. If neither returned: `RAISE EXCEPTION 'insufficient_credits' USING ERRCODE = 'P0002'`.
5. Insert `usage_records` row inside the same transaction. The org_id on the audit row tracks which pool actually paid.

**Permissions**: `REVOKE EXECUTE FROM PUBLIC, anon, authenticated` — only `service_role` can call. Edge Functions invoke it via the service-role client.

**Why team-first with user fallback**: matches the source DynamoDB behaviour where a stale JWT can still have an `org_id` after the team cancels. Falling back to the user pool lets the run complete on user credits rather than failing loudly.

### `topup_team_credits(p_org_id, p_new_cap, p_update_on) RETURNS INT`

MuckRock webhook handler calls this on team-plan changes (seat added, plan renewed). Idempotent — replaying the same `(new_cap, update_on)` is a no-op.

**Flow**:
1. `UPDATE credit_accounts SET balance = balance + GREATEST(0, p_new_cap - monthly_cap), monthly_cap = p_new_cap, update_on = p_update_on WHERE org_id = p_org_id`.
2. If `p_new_cap < balance` (downgrade), clip balance to `p_new_cap`.

**Permissions**: service_role only.

### `reset_expired_credits() RETURNS INT`

Daily cron (00:10 UTC). For every row with `update_on <= CURRENT_DATE`, reset balance to monthly_cap and bump `update_on` by one month. Returns count reset.

## RLS

All four tables `ENABLE ROW LEVEL SECURITY`. No INSERT/UPDATE/DELETE policies are defined — only service_role (via RPCs) can mutate.

| Table | Policy | Operation | Condition |
|---|---|---|---|
| `orgs` | `orgs_read` | SELECT | `id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())` |
| `org_members` | `org_members_read` | SELECT | `user_id = auth.uid()` |
| `credit_accounts` | `credit_accounts_read` | SELECT | `user_id = auth.uid() OR org_id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())` |
| `usage_records` | `usage_records_read` | SELECT | `user_id = auth.uid() OR org_id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())` |

## Cron jobs (from 00026)

| Job | Schedule | Command |
|---|---|---|
| `cleanup-usage-records` | `20 3 * * *` | `DELETE FROM usage_records WHERE expires_at < NOW()` (batch 10k) |
| `reset-expired-credits` | `10 0 * * *` | `SELECT reset_expired_credits()` |

## Edge Functions

| Function | Role |
|---|---|
| `user` (extended) | `GET /user/me` returns `tier`, `credits`, `monthly_cap`, `org_id`, `team{…}`, `upgrade_url`. Reads `user_preferences` + `credit_accounts`. |
| `billing-webhook` | Receives MuckRock webhook, HMAC-verifies, dispatches `applyUserEvent` / `applyIndividualOrgChange` / `applyTeamOrgTopup` / `cancelTeamOrg`. |
| `scout-web-execute`, `scout-beat-execute`, `social-kickoff`, `civic-execute` | Call `decrementOrThrow()` before doing billable work; return 402 on `InsufficientCreditsError`. |

Shared helpers: `supabase/functions/_shared/credits.ts` (`CREDIT_COSTS`, `decrementOrThrow`, `insufficientCreditsResponse`), `_shared/entitlements.ts` (`resolveTier`, `applyUserEvent`, `seedTeamOrg`, `cancelTeamOrg`), `_shared/muckrock.ts` (`fetchUserData`, `fetchOrgData`).

## Data flow

### Login (post-OIDC)

```
Browser → MuckRock OIDC → Supabase /auth/v1/callback → JWT
Browser → GET /functions/v1/user/me
          ↓
          user Edge Function:
            SELECT tier, active_org_id FROM user_preferences
            SELECT balance, monthly_cap, tier FROM credit_accounts
                      (WHERE org_id = active_org_id OR user_id = me)
            COUNT org_members WHERE org_id = active_org_id
          ↓
          { user_id, tier, credits, monthly_cap, org_id, team, upgrade_url }
```

First-time users have no `credit_accounts` row until a MuckRock webhook fires. The `user` Edge Function falls back to `tier: 'free'`, `credits: DEFAULT_CAPS[free]`.

### Scout run

```
pg_cron(scout-<uuid>) → execute-scout → scout-web-execute
                                          ↓
                                          RPC decrement_credits(user_id, 1, scout_id, 'web', 'website_extraction')
                                          ├─ Success → balance -= 1, usage_records INSERT, run proceeds
                                          └─ P0002 → InsufficientCreditsError → 402 JSON
```

Same flow for `scout-beat-execute` (cost 7, `beat`), `social-kickoff` (cost depends on platform), `civic-execute` (cost 10, `civic`; refunded via `refund_credits` when no docs were queued or on error).

### MuckRock webhook (billing change)

```
MuckRock → POST /functions/v1/billing-webhook  (HMAC-SHA256 over timestamp+type+uuids.join(''))
  ├─ type=user                → applyUserEvent(userinfo): resolveTier + upsertUserCredits + upsertUserPreferences + (if team) seedTeamOrg
  ├─ type=organization
  │   ├─ individual=true      → applyIndividualOrgChange: resolve + upsert
  │   ├─ has team entitlement → applyTeamOrgTopup: rpc topup_team_credits(new_cap, update_on)
  │   └─ no team entitlement  → cancelTeamOrg: revert each member's tier + clear active_org_id + cap balance
  └─ unknown                   → 400, logged
```

Signature verification uses constant-time compare; timestamp must be within 120s of server clock.

### Monthly reset

At 00:10 UTC daily, `reset_expired_credits()` walks `credit_accounts` and resets any row whose `update_on` has passed. The MuckRock billing cycle date is the single source of truth — it typically advances when MuckRock sends a webhook, but the fallback reset catches orgs where the webhook was lost.

## Invariants

1. **Exactly one owner per credit_accounts row** (`CHECK` + `UNIQUE`).
2. **Balance can never go below zero** (`CHECK balance >= 0` + the RPC's `WHERE balance >= cost` guard).
3. **Usage row is atomic with the decrement** — same transaction. No fire-and-forget.
4. **Only service_role writes credit_accounts.** No user can self-credit; no trigger can surprise-mutate.
5. **`active_org_id` mirrors actual membership** — the webhook handler keeps it in sync.
6. **Top-up is idempotent** — re-delivering a MuckRock webhook produces the same final state.

## Migration path (DDB → Supabase)

`scripts/migrate/main.ts` Phase 9 seeds:
- `USER#{id}/CREDITS` → `credit_accounts(user_id=…)`
- `ORG#{id}/CREDITS` → `orgs` + `credit_accounts(org_id=…)`
- `ORG#{id}/MEMBER#*` → `org_members`
- Backfills `user_preferences.tier` + `active_org_id` per user

`USAGE#` records are intentionally not migrated — 90-day TTL, fresh start is fine.

Rollback: `docs/migration-rollback.sql` truncates `usage_records`, `credit_accounts`, `org_members`, `orgs` alongside the rest of the app tables.

## Operations

### Spot-check a user's balance

```sql
SELECT tier, monthly_cap, balance, update_on, entitlement_source
  FROM credit_accounts
 WHERE user_id = '<uuid>'
    OR org_id = (SELECT active_org_id FROM user_preferences WHERE user_id = '<uuid>');
```

### Manually credit a user (admin intervention)

```sql
-- Set balance directly (no audit row; use sparingly):
UPDATE credit_accounts
   SET balance = LEAST(balance + :delta, monthly_cap),
       updated_at = NOW()
 WHERE user_id = '<uuid>';
```

Better: run a MuckRock entitlement update so the flow goes through the webhook. Direct writes should be rare and logged in Linear.

### Verify RPC atomicity

```sql
-- Happy path:
INSERT INTO credit_accounts (user_id, tier, monthly_cap, balance)
  VALUES ('11111111-1111-1111-1111-111111111111', 'pro', 1000, 1000);
SELECT * FROM decrement_credits(
  '11111111-1111-1111-1111-111111111111', 7, NULL, 'beat', 'beat');
-- (993, 'user')

-- Insufficient:
SELECT * FROM decrement_credits(
  '11111111-1111-1111-1111-111111111111', 9999, NULL, 'civic', 'civic');
-- ERROR: insufficient_credits (SQLSTATE P0002)

-- Concurrency: run two decrements in parallel, balance never goes negative.
```

## See also

- `docs/muckrock/plans-and-entitlements.md` — tier definitions (upstream spec)
- `docs/muckrock/entitlements-pro-design.md` — Pro design
- `docs/muckrock/entitlements-team-design.md` — Team shared-pool pattern
- `docs/muckrock/webhooks.md` — Webhook payload shapes
- `docs/supabase/auth-users.md` — upstream identity + user_preferences
- `supabase/functions/_shared/credits.ts` / `_shared/entitlements.ts` / `_shared/muckrock.ts` — runtime helpers
