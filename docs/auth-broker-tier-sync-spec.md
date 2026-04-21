# PR 2a — Auth broker tier + org + webhook sync (post-cutover)

**Branch:** off `main` (cutover merged in PR 53 at 942fd3c)
**Follows:** `docs/auth-broker-cutover.md`
**Status:** draft — not yet implemented
**Blocks:** any production Team subscriber login on v2; any post-cutover MuckRock plan change sync

---

## Context

The auth broker shipped in PR 53 does the minimum needed to sign users in on Supabase:

1. Verify the MuckRock OAuth handshake.
2. `supabase.auth.admin.create_user({id: muckrock_uuid, email, email_confirm: True})` — idempotent on duplicate.
3. `supabase.auth.admin.generate_link({type: 'magiclink'})` and 302 to the `action_link`.

It does **not** resolve tier, create org rows for Team plans, seat users into `org_members`, or react to MuckRock plan-change webhooks. The plan-change webhook is gated 503 via `MUCKROCK_WEBHOOK_PAUSED=true` on Render.

v1 logic this PR ports lives in:
- `backend/app/services/user_service.py` — `resolve_tier`, `get_or_create_user`, `update_tier_from_org`, `claim_seat`, `cancel_team_org`
- `backend/app/routers/auth.py` — legacy `handle_webhook` branches (user, organization-individual, organization-team)
- `docs/muckrock/entitlements-team-design.md` — the v1 Team design (shared credit pool, ORG# + ORGMEM# records)
- `docs/muckrock/plans-and-entitlements.md` — tier rank table + default caps

v2 schema is ready:
- `public.orgs` — organization row, keyed on MuckRock org UUID
- `public.org_members` — user ↔ org membership + role
- `public.credit_accounts` — `user_id` OR `org_id` (exactly one) owns the row; `tier`, `monthly_cap`, `balance`, `update_on`, `entitlement_source`

What is currently correct on v2 for the 69 users migrated tonight:
- `auth.users`: 69 rows with preserved UUIDs — ✓
- `credit_accounts`: 69 rows keyed on `user_id` with tier (`free` x 67, `pro` x 2) and balances carried over — ✓

What is currently incorrect (silently) on v2:
- A new Team login post-cutover would land as `free` — ✗
- A MuckRock `organization` webhook (plan upgrade / team invite / plan cancel) is absorbed by the 503 gate — ✗
- The 2 pro users in DDB have their balances but **not** their `update_on` reset-date populated (need to cross-check)

Zero real Team subscribers exist in production today (DDB `ORG#` record count = 0, `tier=team` count = 0 across all PROFILE records), so this gap is a future-subscriber problem, not a data-loss problem. It must be closed before the Team plan is publicly bookable on v2.

---

## Goals

1. When any user completes OAuth, the broker resolves their tier from `userinfo.organizations` and keeps `credit_accounts` consistent.
2. When a MuckRock webhook fires for a `user` or `organization` event, the handler updates Supabase state via `supabase-py` admin + PostgREST.
3. `MUCKROCK_WEBHOOK_PAUSED` flips to `false` only after (1) and (2) are live and verified.
4. No regressions for the 67 free + 2 pro users who successfully migrated.

## Non-goals

- **No** team-scoped scouts, feed, or project sharing. Out of scope per `docs/muckrock/entitlements-team-design.md` — seat-only Team plan.
- **No** DDB fallback. v1 code paths under `user_service.py` remain dormant and are deleted by PR 4.
- **No** retroactive reconciliation of any webhook events absorbed by the 503 gate during the cutover window. If a plan change fired during that window, reconcile manually from MuckRock admin API.

---

## Design

### Shared helper — `backend/app/services/supabase_entitlements.py` (new)

Centralize all Supabase writes so the callback and webhook call the same code path. Owns:

```python
class SupabaseEntitlements:
    """
    Resolve MuckRock entitlements → Supabase orgs/org_members/credit_accounts.
    Used by BOTH the OAuth callback (on every login) and the webhook handler.
    """
    def __init__(self, admin: Client): ...

    async def sync_user(self, muckrock_uuid: str, email: str, userinfo: dict) -> SyncResult:
        """
        Idempotent end-to-end sync for a single user. Steps:
          1. resolve_tier(userinfo['organizations']) → (tier, monthly_cap, update_on, org_uuid)
          2. If tier == 'team':
             - Upsert orgs{id=org_uuid, name, max_seats=userinfo org.max_users, monthly_cap}
             - Upsert org_members{org_id, user_id, role='member', seat_claimed_at=now}
             - Upsert credit_accounts{org_id=org_uuid, user_id=NULL, tier, monthly_cap, balance on first create, update_on, entitlement_source='muckrock'}
             - Upsert credit_accounts row for user_id pointing at org (or just delete the per-user row if one exists)
          3. Else (free/pro):
             - Drop any org_members rows for this user_id (user may have cancelled team membership)
             - Upsert credit_accounts{user_id, org_id=NULL, tier, monthly_cap, balance preserved on existing or set to cap on first create, update_on, entitlement_source='muckrock'}
        Returns SyncResult with {tier, org_id|None, changed_fields}.
        """

    async def sync_org(self, org_uuid: str, org_data: dict) -> SyncResult:
        """
        Webhook 'organization' event handler. Fetches org from MuckRock, resolves
        entitlement for that org, updates orgs + credit_accounts. Does NOT touch
        membership (membership changes come via user events).
        """

    async def cancel_org(self, org_uuid: str) -> None:
        """
        MuckRock org deletion / plan cancellation. Marks orgs.status='cancelled',
        zeroes the shared credit_accounts balance, and re-seats each member back
        to their individual tier by calling sync_user against each member's
        userinfo (fetched fresh from MuckRock /api/users/{uuid}).
        """
```

`resolve_tier` logic mirrors v1 exactly (`TIER_RANK = {'free': 0, 'pro': 1, 'team': 2}`, pick highest-ranked non-cancelled entitlement across all orgs). Copy the function from `user_service.py` verbatim with the v2 return shape.

### OAuth callback — `backend/app/routers/auth.py`

After the existing `admin.create_user` + `admin.generate_link`, before the `RedirectResponse`, call:

```python
entitlements = SupabaseEntitlements(supabase_admin)
await entitlements.sync_user(muckrock_uuid, email, userinfo)
```

Swallow-and-log any exception from `sync_user` — login should NOT fail because entitlement sync errored; we can reconcile via webhook. Log at ERROR level with `muckrock_uuid` so the failure is discoverable.

### Webhook — `backend/app/routers/auth.py::handle_webhook`

Remove the `MUCKROCK_WEBHOOK_PAUSED` 503 short-circuit. Replace the DynamoDB event branches with:

```python
if event_type == "user":
    for uuid in uuids:
        userinfo = await muckrock.fetch_user_data(uuid)
        await entitlements.sync_user(uuid, userinfo["email"], userinfo)

elif event_type == "organization":
    for uuid in uuids:
        try:
            org_data = await muckrock.fetch_org_data(uuid)
        except MuckRockClientError as e:
            if e.status_code == 404:
                await entitlements.cancel_org(uuid)
                continue
            raise
        if org_data.get("individual"):
            # Individual org — update the owner's tier (org_uuid == user_uuid)
            userinfo = await muckrock.fetch_user_data(uuid)
            await entitlements.sync_user(uuid, userinfo["email"], userinfo)
        else:
            # Team org — update shared pool
            await entitlements.sync_org(uuid, org_data)
```

HMAC verification, timestamp window, and the 400/401 error paths stay exactly as they are today.

### Render env vars

- `MUCKROCK_WEBHOOK_PAUSED` → flip to `false` after this PR deploys. Leave the env var in place so we can re-pause during any future incident.

### Settings

- `backend/app/config.py`: `muckrock_webhook_paused` stays as a gate. No new settings needed (reuses `supabase_url`, `supabase_service_key`, `muckrock_client_id/secret`).

---

## Data-migration tasks (one-shot, run once after deploy)

The initial migration (PR 53 Event 1) correctly wrote `credit_accounts` for the 69 users, but it used v1 DDB tier data only. The 2 pro users and any existing team orgs (currently zero) need their `update_on` fields populated to match MuckRock's current `update_on`. One-shot script:

**File:** `scripts/backfill-entitlements.ts` (Deno, same shape as `scripts/migrate/main.ts`)

1. For each row in `auth.users`:
   - `muckrock.fetch_user_data(uuid)` → userinfo.
   - Call `SupabaseEntitlements.sync_user` via HTTP against the broker's internal endpoint (or replicate the logic in Deno).
2. Report: users processed, tier changes detected, org rows created, errors.

Run once after PR 2a deploys + before flipping `MUCKROCK_WEBHOOK_PAUSED=false`. Idempotent, so safe to re-run.

---

## Test plan

### Unit tests (pytest)

**New file:** `backend/tests/unit/shared/test_supabase_entitlements.py`

- `test_sync_user_free_tier_creates_credit_account_keyed_on_user`
- `test_sync_user_pro_tier_preserves_balance_on_re_sync`
- `test_sync_user_team_tier_creates_org_and_seat_and_shared_credit_account`
- `test_sync_user_downgrade_from_team_to_free_drops_membership_and_restores_user_account`
- `test_sync_user_with_multiple_orgs_picks_highest_tier`
- `test_sync_user_with_no_entitlements_defaults_to_free`
- `test_sync_org_cancelled_by_muckrock_fans_out_to_member_reseat`

**Mock strategy:** patch `supabase_admin.auth.admin.*` and the `postgrest` client. No live Supabase calls in unit tests. Use real JSON fixtures from `docs/muckrock/userinfo-and-orgs.md:91-126` example.

**New file:** `backend/tests/unit/auth/test_auth_router_webhook.py`

- `test_webhook_user_event_calls_sync_user`
- `test_webhook_organization_individual_calls_sync_user_with_org_uuid_as_user_uuid`
- `test_webhook_organization_team_calls_sync_org`
- `test_webhook_organization_404_calls_cancel_org`
- HMAC, timestamp, and missing-fields tests are already in `test_auth_router.py` — keep them.

### Integration tests

Local `supabase start` + a mocked MuckRock fixture server. Script runs:

1. Login as a MuckRock user with only a free tier → assert `credit_accounts` row appears with `tier='free'`, `monthly_cap=100`.
2. Webhook-simulate an `organization` event upgrading that user's individual org to `cojournalist-pro` → assert the same user's `credit_accounts` row flips to `tier='pro'` with higher cap, balance preserved.
3. Webhook-simulate an `organization` event creating a `cojournalist-team` org with 3 members → assert `orgs` row, 3 `org_members` rows, one shared `credit_accounts` row keyed on `org_id`.
4. Webhook-simulate a `user` event adding a 4th member to the team → assert `org_members` gets the new row, shared credit_accounts row unchanged.
5. Webhook-simulate `organization` 404 for the team org → assert all 4 members re-seat to their prior tier, `orgs.status='cancelled'`.

### Manual smoke (pre-`MUCKROCK_WEBHOOK_PAUSED=false`)

1. Run `scripts/backfill-entitlements.ts` against prod Supabase in DRY_RUN.
2. Compare output to current `credit_accounts` — expect no changes for the 2 pro users (balances preserved), possibly `update_on` populated where it was null.
3. Run in write mode.
4. Verify one pro user logs in → their tier stays pro, balance unchanged.
5. Flip `MUCKROCK_WEBHOOK_PAUSED=false` on Render dashboard.
6. Manually fire a no-op webhook from MuckRock admin (re-send last event) → verify 200 response + matching `credit_accounts` row.

---

## Rollback

Failure in the OAuth callback's `sync_user` call is swallowed by design — login keeps working, tier is stale. That is the soft-fail mode.

Hard failure (deploy breaks login) rolls back via Render "Rollback to previous deploy" → returns to the current state where the 503 gate is still in place and existing users keep logging in at their migrated tier. No Supabase data cleanup needed.

If `scripts/backfill-entitlements.ts` corrupts `credit_accounts`, restore via the snapshot taken pre-run:

```bash
deno run -A scripts/snapshot-credit-accounts.ts --out /tmp/credit_accounts.$(date +%s).json
```

(Script to write: simple `SELECT * FROM public.credit_accounts` → JSON → S3 or local.)

---

## Acceptance

- [ ] `pytest tests/unit/` — new tests pass, no regressions.
- [ ] Integration test covers all 5 flows above, green.
- [ ] `backfill-entitlements.ts --dry-run` against prod Supabase shows no unexpected diffs.
- [ ] After merge + deploy: a pro user logs in and their `credit_accounts` row is untouched except `updated_at` + `update_on`.
- [ ] `MUCKROCK_WEBHOOK_PAUSED=false` and one real webhook event processes successfully with 200 response.
- [ ] `docs/auth-broker-cutover.md` decisions log updated — webhook port no longer deferred.

## Out-of-scope follow-ups (later PRs)

- Team-scoped feed / projects / scouts (PR 2b or dedicated epic).
- Self-serve team org management UI (invite members, promote to admin, revoke seats). Currently handled entirely on the MuckRock side.
- Credit reset cron: every 1st-of-month, reset `balance = monthly_cap` where `update_on <= today`. Likely a `pg_cron` job; spec separately under `docs/supabase/cron-jobs.md`.
