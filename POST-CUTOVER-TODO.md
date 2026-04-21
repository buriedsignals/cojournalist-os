# Post-Cutover Follow-Ups

Tracking known issues and deferred work that surfaced during the
v2 auth-broker cutover on 2026-04-21. None of these block production
auth or data access; they are polish + feature gaps to work through in
the following days.

**Live today:** MuckRock OAuth broker, Supabase-backed data, 73 auth.users,
~300 rows migrated across scouts/runs/units/credits/post_snapshots, Render
deploy auto-rolling from `main`, DDB snapshotted (`pre-cutover-20260421-2137`).

## High-priority follow-ups

### 1. Team-plan tier + org sync in the broker (spec written)

**Spec:** `docs/auth-broker-tier-sync-spec.md` (PR 2a scope)

The OAuth callback today resolves *identity* but not *entitlement* — a
MuckRock user with `cojournalist-team` lands as default `free` tier.
MuckRock plan-change webhooks return 503 (paused via
`MUCKROCK_WEBHOOK_PAUSED=true`). Port `user_service.resolve_tier` +
`claim_seat` + `cancel_team_org` to v2 via a new `SupabaseEntitlements`
helper called from both the callback and the webhook. Blocks any new
Team-plan signup on v2.

### 2. Frontend `/scrapers/*` → Edge Function path migration

`frontend/src/lib/api-client.ts` still calls v1 paths (`/scrapers/active`,
`/scrapers/run-now`, `/scrapers/monitoring`, `/scrapers/monitoring/validate`).
Today they resolve against FastAPI via `VITE_API_URL=/api` — that's the
cutover-night workaround. The proper v2 target is the `scouts` Edge Function
at `/functions/v1/scouts[/{id}/{run|pause|resume}]`. Rename the api-client
methods, adjust response-shape handling (v1 returned `{scrapers:
[{scraper_name}]}`, v2 returns paginated `{items: [{id, name, ...}]}`),
then flip `VITE_API_URL` to `https://gfmdziplticfoakhrfpt.supabase.co/functions/v1`.
PR 4 (FastAPI surface deletion) depends on this landing first.

## Medium-priority follow-ups

### 3. Run Now spinner should wait for run completion

v1 behavior: click Run Now → spinner spins until the scout run finishes
(~5-20s) → toast with the result. v2 behavior: spinner stops on HTTP 202
(the fire-and-forget create-run response) within ~1s, giving the impression
the run was skipped. The run does complete in the background; the UI just
doesn't reflect it.

Fix: after POSTing the run-now request, poll `GET /api/scout_runs/:id`
every ~2s (or subscribe via Supabase realtime) until `status != 'running'`,
then stop the spinner and toast the result. Non-blocking — runs do succeed,
users just need to refresh the run history to see them.

### 4. PageScoutModal UI doesn't match the design system

The "Set Up Page Scout" modal (attached screenshot) is white + purple while
the rest of the app uses the beige/cream palette. Visual regression from
the UI refactor, not a data regression. Scope: `frontend/src/lib/components/modals/PageScoutModal.svelte`
— replace design tokens to match `var(--color-bg)` / `var(--color-primary-deep)`
used elsewhere.

### 5. Credits pill font alignment

Small visual issue on the "976 CREDITS" pill — numeric + label baselines
don't align with the border. Single-file CSS fix.

## Low-priority / housekeeping

### 6. PR 4 — FastAPI non-auth surface deletion (T+24/48h)

Per the cutover plan: delete `user_service.py`, `session_service.py`, and
the non-auth routers after Supabase has been stable for a day. Unblocks
PR 6 (OSS mirror cleanup) and PR 5b (remove AWS env vars from Render).

### 7. DDB decommission window (after T+7d of clean runs)

Keep the `pre-cutover-20260421-2137` DDB backups retained until at least
T+30d. Once confident, snapshot final state to S3 Glacier, then delete
the `scraping-jobs` and `information-units` tables + Lambda + EventBridge
Scheduler + API Gateway. Stops the AWS bill from the v1 infrastructure.

### 9. Port `backend/scripts/bump_credits.py` to Supabase

Script reads `MUCKROCK_CLIENT_ID` + secret to look up a user UUID by
email, then writes a `CREDITS#` row in DynamoDB to bump their balance.
Post-cutover, credits live in `public.credit_accounts` keyed on
`user_id`. Replace the boto3/DynamoDB writes with a `supabase-py`
upsert against `credit_accounts` (or a SECURITY DEFINER RPC if you'd
rather keep the bump-credits action audit-logged). Email→UUID lookup
via MuckRock stays — that's still the source of truth for identity.

Until ported, the script is a no-op against production.

### 8. Mirror OSS strip-oss.sh broader cleanup

Several `sed` edits I added during cutover were surgical fixes to keep
the mirror validation passing. The cutover plan PR 6 rewrites strip-oss.sh
to `rm -rf backend/` and streams a slimmed OSS tree. Plenty of room to
consolidate the ad-hoc sed patches once the FastAPI surface is gone in
PR 4.

## Known non-issues (not to re-investigate)

- `Failed to check active jobs for notifications` in console: same
  root cause as follow-up 2. Will resolve either by the `VITE_API_URL=/api`
  deploy tonight (short-term) or by follow-up 2 (long-term).
- `/functions/v1/scouts` returns 401 for unauthenticated requests: that's
  the Edge Function's auth gate. Normal and expected.
- `MUCKROCK_WEBHOOK_PAUSED=true` on Render: deliberate, gated by the
  PR 2a rollout above.
