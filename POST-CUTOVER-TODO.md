# Post-Cutover Follow-Ups

> **NEW SESSION? START HERE.** Read [Handoff for fresh session](#handoff-for-fresh-session-state-as-of-2026-04-22-0145) first.

Tracking known issues and deferred work that surfaced during the
v2 auth-broker cutover on 2026-04-21. None of these block production
auth or core dashboard data; they are polish + feature gaps to work
through in the following days.

**Live today:** MuckRock OAuth broker, Supabase-backed data, 73 auth.users,
~300 rows migrated across scouts/runs/units/credits/post_snapshots, Render
deploy auto-rolling from `main`, DDB snapshotted (`pre-cutover-20260421-2137`).

---

## Handoff for fresh session (state as of 2026-04-22 01:45)

### What works in production right now

- MuckRock OAuth login flow → lands on dashboard with real user data ✓
- Dashboard `/` renders: scout list (`/scouts` EF), Inbox units (`/units` EF), user profile (`/user/me` EF) ✓
- "Set Up Page Scout" modal saves via `POST /scouts` EF ✓ (untested with real form data — verify in browser)
- "Run Now" fires-and-forgets to `/scouts/:id/run` (UI spinner stops on 202; doesn't reflect actual completion — POST-CUTOVER-TODO #3 spinner regression)
- Inbox location/topic filter dropdowns: client-side aggregated from `/units` page (200-unit cap; degraded UX past that)
- `/extract/*` (Scrape feature): mapped to `/ingest` EF + direct Supabase query for status

### What's broken / partially-broken in production right now

| Feature | Status | Blocker |
|---|---|---|
| Inbox location/topic filtering at scale | Caps at 200 units client-side | Need server-side `topic` query param on `/units` EF + a `distinct_locations`/`distinct_topics` RPC. ~30 min EF patch + redeploy. |
| Auto-select export (`autoSelectUnits` in api-client) | Stubbed/breaks (api-client still calls `/export/auto-select` against EF URL → 404) | EF source written at `supabase/functions/export-select/index.ts` but **NOT yet deployed**. See "Unfinished work" below. |
| API Keys management UI (`/v1/keys` in PreferencesModal) | Throws on click | No `api_keys` table in Supabase. Needs schema migration + new EF + RLS. |
| MuckRock plan-change webhook | 503-paused | PR 2a deferred — see `docs/auth-broker-tier-sync-spec.md` |
| Team-plan tier resolution at login | Defaults Team users to free tier | Same as above (PR 2a) |
| `/api/scrapers/*`, `/api/scouts`, `/api/user/me` (FastAPI direct) | 500 with `AttributeError: scraper_lambda_arn` | Frontend doesn't hit these anymore; only matters if `cojo` CLI or external API client targets them. PR 4 (data router deletion) makes the error go away by deleting the offending routers. |

### Unfinished work in this branch (uncommitted as of session end)

**ONE file uncommitted:** `supabase/functions/export-select/index.ts` (LLM auto-selection EF source). It's a complete, well-typed implementation but **never deployed and never tested**. To finish:

1. **Bundle it for deploy.** The Supabase deploy tool requires `_shared/*` deps to be either uploaded as separate files or inlined into the index.ts. Working bundler script written at `/tmp/inline.ts` (see "How I bundled EFs tonight" in [Operational notes](#operational-notes-tools--patterns) below). Re-create the bundle from the committed source.
2. **Deploy via `mcp__supabase__deploy_edge_function`** with `name=export-select`, `verify_jwt=true`, `entrypoint_path=index.ts`, files=[bundled inline.ts only].
3. **Verify with the EF probe script** (see `scripts/preflight-uuid-validation.ts` for the JWT-minting pattern; my version was at `/tmp/probe_efs.ts` but it's gone with the temp dir). Quick rebuild: mint JWT for Tom's UUID `c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c`, POST to `/functions/v1/export-select` with a small units array, expect 200 + `{selected_unit_ids, selection_summary}`.
4. **Wire frontend.** Update `frontend/src/lib/api-client.ts` `autoSelectUnits` method (currently calls `/export/auto-select` which 404s on EF) to call `/export-select`. Body shape already matches.
5. **Add fallback.** On EF 500/timeout, return `{selected_unit_ids: input.units.slice(0, 10).map(u => u.unit_id), selection_summary: 'AI selection unavailable; showing first 10 units.'}` so UI doesn't crash if Gemini quota exceeded.

### Critical access info for the new session

- **Repo:** `/Users/tomvaillant/buried_signals/tools/cojournalist-migration`. Two clones existed today; `cojournalist-migration` is the canonical one. The old `cojournalist/` clone can be `rm -rf`'d (see commit `3e1c833`).
- **Secrets:** `supabase-keys.txt` at repo root (gitignored) has `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL` (Supavisor v2 pooler at `aws-1-eu-west-1.pooler.supabase.com:6543`). `.env` at repo root has AWS, MuckRock, Render, Resend, OpenRouter, Gemini, Stripe keys.
- **Render service ID:** `srv-d49kgfje5dus73cpmlkg`. API key is in `.env` as `RENDER_API_KEY`. Use `curl -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/...` for everything; the MCP requires workspace selection prompt that I deliberately didn't trigger in auto mode.
- **Supabase MCP project_id:** `gfmdziplticfoakhrfpt`. Region: `eu-west-1`. Tools: `mcp__supabase__execute_sql`, `mcp__supabase__deploy_edge_function`, `mcp__supabase__get_edge_function`, `mcp__supabase__list_edge_functions`, `mcp__supabase__apply_migration`, `mcp__supabase__list_migrations`.
- **Tom's user UUID for testing:** `c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c` (owns the `Ticket Hyrox` scout, useful sentinel for "did I see real data" verification).

### How to mint a real Supabase JWT for direct EF probing (replaces deploy-debug loop)

Saved earlier at `/tmp/probe_efs.ts` (now deleted). Recreate:

```ts
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_KEY")!,
  { auth: { persistSession: false, autoRefreshToken: false } });
const { data: u } = await admin.auth.admin.getUserById("c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c");
const { data: link } = await admin.auth.admin.generateLink({
  type: "magiclink", email: u.user!.email!,
  options: { redirectTo: "http://localhost/auth/callback" },
});
const r = await fetch(link.properties!.action_link, { redirect: "manual" });
const hash = r.headers.get("location")!.split("#")[1];
const jwt = new URLSearchParams(hash).get("access_token")!;
console.log(jwt);
```

Run as `set -a && source .env && source supabase-keys.txt && set +a && deno run --allow-net --allow-env <script>`. **This is the fastest debug primitive in this repo — use it before any redeploy-and-curl loop.** Edge Function probes return shape diffs in seconds against prod, no browser, no Render rebuild.

### Operational notes (tools + patterns)

- **EF deploy via MCP**: bundle `_shared/*` deps inline into `index.ts` because the deploy tool's module resolver doesn't reach across function dirs reliably. Python bundler pattern: read each `_shared/*.ts`, strip its imports, concat in dep order (`errors → cors → supabase → responses → log → gemini → auth`), then concat the index.ts (with its imports also stripped). Result is a single self-contained file. Working approach used for export-select tonight.
- **Render env-var trap**: see [the dedicated section in CLAUDE.md](CLAUDE.md#frontend-env-var-trap--read-this-before-changing-any-public_-or-vite_-config). Anything `PUBLIC_*` or `VITE_*` lives in `Dockerfile` ENV (hardcoded) or `frontend/.env.production` (committed). Never in Render envVars (silently ignored). Backend secrets (SUPABASE_SERVICE_KEY, DATABASE_URL, MUCKROCK_*) live on Render only.
- **Adapter pattern in api-client.ts**: every legacy method that hits a path no longer on the backend has been rewritten as an adapter — calls the EF, reshapes response back to v1 contract so UI components stay untouched. See `getActiveJobs`, `deleteActiveJob`, `runScoutNow`, `getUserUnitLocations` for examples. New EF endpoints follow this pattern: small in-method shape mapping, no UI changes.
- **DON'T touch FastAPI data routers**. They're broken (`scraper_lambda_arn` AttributeError) and going away in PR 4. Frontend no longer calls them. The auth broker (`/api/auth/login`, `/api/auth/callback`, `/api/auth/webhook`) is the only FastAPI surface that matters.

### What I'd suggest doing first in the new session

1. **Verify the dashboard still works.** Refresh browser, sign in if needed, confirm Tom's scouts + Inbox render. (Should be fine; no changes since session end.)
2. **Commit + ship export-select.** It's the only loose end I left on disk. ~15 min: bundle, deploy via MCP, probe with JWT script, wire api-client, PR + admin-merge.
3. **Then `/v1/keys`** (item #4 below). Schema + EF + RLS + api-client. ~45 min.
4. **Then PR 4 cleanup** (delete FastAPI data routers). Closes the `/api/scrapers/*` 500s and removes the half-removed AWS plumbing entirely. ~30 min.
5. **Then PR 2a** (Team tier sync, spec at `docs/auth-broker-tier-sync-spec.md`). Required before any real Team user signs in. ~2-3 hours.
6. Run-now spinner + credits-pill CSS are pure cosmetic — schedule whenever.

---

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

### 4b. `/v1/keys` API key management — needs schema + new EF

**Why it's hard:** no `api_keys` table exists in Supabase. The whole feature needs:

1. **Migration** `supabase/migrations/00xxx_api_keys.sql`:
   ```sql
   CREATE TABLE public.api_keys (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
     key_hash text NOT NULL,             -- store hash, not the key itself
     key_prefix text NOT NULL,           -- "cj_xxxx" for display
     name text NOT NULL,
     created_at timestamptz NOT NULL DEFAULT now(),
     last_used_at timestamptz
   );
   CREATE INDEX idx_api_keys_user_id ON public.api_keys(user_id);
   CREATE INDEX idx_api_keys_key_hash ON public.api_keys(key_hash);
   ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
   CREATE POLICY api_keys_owner ON public.api_keys
     FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
   ```
   Apply via `mcp__supabase__apply_migration`.

2. **Edge Function** `supabase/functions/api-keys/index.ts`:
   - `GET /api-keys` → list (returns `key_id, key_prefix, name, created_at, last_used_at`; never `key_hash`)
   - `POST /api-keys {name}` → generate new key (`cj_<24 random chars>`), store `key_hash = sha256(key)`, return `{key, key_id, key_prefix, name, created_at}` ONCE (key never retrievable again)
   - `DELETE /api-keys/:id` → revoke (delete row)
   Use `requireUser` for auth, `getUserClient` for RLS-scoped reads/writes.

3. **api-client wire-up** in `frontend/src/lib/api-client.ts`:
   - `createApiKey` → POST `/api-keys`
   - `listApiKeys` → GET `/api-keys` (reshape to `{keys: [...], count}`)
   - `revokeApiKey` → DELETE `/api-keys/:id`

4. **Validation flow for the v1 public API.** When a request comes in with `Authorization: Bearer cj_xxxxx`, hash it and look up `api_keys` to find the user_id. This is more complex — needs a `validate_api_key` SECURITY DEFINER RPC. Defer this part until after the management UI ships.

Estimate: 30-45 min for items 1-3 (management UI works; key validation for actual API requests follows later).

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

## Reference — Render env-var consolidation path

Today's Render service has 5+ Supabase-related env vars because the
FastAPI surface still owns the data path. Each has a distinct consumer:

| Env var | Used by | Why needed today |
|---|---|---|
| `SUPABASE_URL` | FastAPI broker (`routers/auth.py`) | Build admin REST calls (`admin.create_user`, `admin.generate_link`) |
| `SUPABASE_SERVICE_KEY` | FastAPI broker | Auth header for admin calls (bypasses RLS) |
| `SUPABASE_JWT_SECRET` | `adapters/supabase/auth.py` HS256 fallback | Legacy symmetric-token branch — can be dropped once we're confident no HS256 tokens are in flight (TTL drained, see PR for ES256+JWKS) |
| `DATABASE_URL` | asyncpg pool in `adapters/supabase/connection.py` | Direct Postgres reads from FastAPI data routers (scouts, units, scraper, etc.). Uses Supavisor v2 pooler at `aws-1-eu-west-1.pooler.supabase.com:6543` (NOT the legacy `aws-0` pattern, NOT the IPv6-only direct host) |
| `PUBLIC_SUPABASE_URL` | Frontend bundle (build-time) | `auth-supabase.ts` reads via `import.meta.env.PUBLIC_SUPABASE_URL` to init the browser supabase-js client that calls `setSession()` after magiclink hop |
| `PUBLIC_SUPABASE_ANON_KEY` | Frontend bundle (build-time) | Same — supabase-js needs the anon key to identify the project |

### Why "I saw my scouts earlier" worked without `DATABASE_URL`

Earlier in tonight's cutover, `VITE_API_URL` pointed at
`https://gfmdziplticfoakhrfpt.supabase.co/functions/v1`. Frontend data
calls hit Supabase Edge Functions directly. Edge Functions run *inside*
Supabase's infrastructure and read Postgres via the internal network
using the service-role key — they never go through FastAPI, never need
`DATABASE_URL` from Render.

When we flipped `VITE_API_URL=/api` to make the legacy `/scrapers/*`
routes reachable on FastAPI, every data call started going through
the FastAPI → asyncpg → Postgres path. That path needs `DATABASE_URL`.
It was unset → asyncpg fell back to localhost → `ConnectionRefusedError`
→ 500 on `/api/user/me`, `/api/scouts`, `/api/units`,
`/api/scrapers/active`. Adding the pooler URL to Render fixed it.

### Long-term steady state (after follow-up #2 lands)

Once `frontend/src/lib/api-client.ts` calls Edge Functions for data
(rename `/scrapers/*` → `/scouts`, etc.) and PR 4 deletes the FastAPI
data routers + adapters, the FastAPI service shrinks to **just
`/api/auth/*`**. At that point:

- `DATABASE_URL` — can be removed from Render (no asyncpg pool needed).
- `SUPABASE_SERVICE_KEY` — can be removed (auth broker only needs URL).
- `SUPABASE_JWT_SECRET` — can be removed (PR 2a webhook port + ES256-only validation).
- `SUPABASE_URL` — kept for the broker.
- `PUBLIC_SUPABASE_URL` + `PUBLIC_SUPABASE_ANON_KEY` — only used at frontend build step; can stay in `.env.production` (already are) and be dropped from Render altogether.

Steady-state Render Supabase footprint: **1 env var** (`SUPABASE_URL`).
Today's footprint: 5+. The cleanup is gated on follow-up #2.

## Known non-issues (not to re-investigate)

- `Failed to check active jobs for notifications` in console: same
  root cause as follow-up 2. Will resolve either by the `VITE_API_URL=/api`
  deploy tonight (short-term) or by follow-up 2 (long-term).
- `/functions/v1/scouts` returns 401 for unauthenticated requests: that's
  the Edge Function's auth gate. Normal and expected.
- `MUCKROCK_WEBHOOK_PAUSED=true` on Render: deliberate, gated by the
  PR 2a rollout above.
