# Auth + data migration — MuckRock OIDC cutover

**Goal.** Move the ~50 existing SaaS users from AWS DynamoDB + FastAPI session cookies to Supabase (project `gfmdziplticfoakhrfpt`) in a single 4-hour maintenance window. End state: MuckRock authenticates through Supabase Auth as a **Custom OIDC provider**; all data lives in Supabase; FastAPI on Render is decommissioned.

**Prerequisite.** Every item in `docs/v2-followups.md` is complete first — the new SvelteKit workspace, `cojo` binary releases, and MCP OAuth server must already be live (pointed at the old FastAPI backend), so this window is about auth + data only, not UI + auth + data.

**Single change MuckRock-side.** One email to MuckRock's admin asking them to add **one** new redirect URI on OAuth app `879742`. That's the only coordination with MuckRock that this migration needs.

---

## Architecture: MuckRock as Custom OIDC on Supabase Auth

Supabase rolled out Custom OIDC providers in late 2025. It's the native path for a third-party OIDC IdP: Supabase handles discovery, token exchange, userinfo, and session issuance entirely.

**Flow after cutover:**

```
Browser  ────► https://gfmdziplticfoakhrfpt.supabase.co/auth/v1/authorize?provider=muckrock
              └─► 302 to accounts.muckrock.com/openid/authorize (same as today)
                   └─► MuckRock login
                        └─► 302 back to https://gfmdziplticfoakhrfpt.supabase.co/auth/v1/callback
                             └─► Supabase exchanges code, fetches userinfo, issues JWT
                                  └─► 302 to https://cojournalist.ai/auth/callback?access_token=...
                                       └─► Frontend stores token, calls /functions/v1/* directly
```

Key decisions:

- **User IDs are preserved.** Before cutover, every existing MuckRock user gets pre-seeded in `auth.users` via `supabase.auth.admin.createUser({ id: <muckrock_uuid>, email, email_confirm: true })`. When that user later signs in via OIDC, Supabase matches by email and links the identity to the existing row — no new UUID is generated. All migrated `user_id` FKs continue to resolve.
- **FastAPI on Render is removed from the hot path.** No auth shim, no session cookies, no `/api/auth/*`. FastAPI stays on Render for 30 days as cold-standby rollback insurance, then is torn down.
- **MuckRock's OAuth app 879742 gets ONE new redirect URI** added alongside the existing one. No webhook changes, no secret rotation, no provider rename.

### Why this is clean

- No custom JWT signing in application code — Supabase owns the token lifecycle end-to-end
- Refresh tokens Just Work via the Supabase JS client
- Removing the FastAPI auth path closes an entire attack surface
- Users see the same MuckRock login UI; only the domain in the URL bar briefly flashes `gfmdziplticfoakhrfpt.supabase.co` during the redirect dance

---

## Pre-window work (must land before scheduling the window)

### 1. MuckRock coordination (lead time: days)

Email MuckRock admin:

> Hi — we're migrating coJournalist's auth from our FastAPI to Supabase Auth. For OAuth app client_id `879742`, can you add the redirect URI `https://gfmdziplticfoakhrfpt.supabase.co/auth/v1/callback` alongside the existing `https://cojournalist.ai/api/auth/callback`? We'll keep both active during a transition; the old one stays live for 7 days post-cutover then we'll ask you to remove it.
>
> No other changes — same scopes (`openid profile uuid organizations email preferences`), same client secret. Confirming: will reply when added.

Wait for their confirmation email before proceeding.

### 2. Code work — frontend auth swap (land before the window)

`frontend/src/lib/stores/auth-supabase.ts` already exists from the OSS strip. Wire it up as the primary auth store (not just the OSS fallback):

- On login button click: `supabase.auth.signInWithOAuth({ provider: 'muckrock', options: { redirectTo: 'https://cojournalist.ai/auth/callback' } })` — using the Supabase JS client against the cloud project
- On `/auth/callback` page load: parse `access_token` from the URL hash, `supabase.auth.setSession({ access_token, refresh_token })`, redirect to `/workspace`
- `api-client.ts` (already refactored in the UI work) reads the token from `supabase.auth.getSession()` and sends as Bearer

Merge as a PR before the window so it's already reviewed and built, but don't promote to production until the window begins.

### 3. Code work — delete FastAPI auth routes (land in the same PR)

In the cutover PR:

- Delete `backend/app/routers/auth.py` (MuckRock OAuth handler)
- Delete `backend/app/services/muckrock_client.py`
- Remove the `auth` router mount from `backend/app/main.py`
- Leave `require_admin` for the admin dashboard (which stays SaaS-only) — but it now reads the `Authorization: Bearer` JWT like Edge Functions do

These deletions won't be deployed to Render during the window; they land on `main` after the window closes, as part of the decommission.

### 4. Preflight validation (all must pass against `supabase start` locally)

Run the preflights in order; green on each is the gate to scheduling the window.

#### Preflight 1 — auth.admin.createUser preserves UUID

```ts
// Locally (e.g. scripts/preflight-1.ts, deno):
import { createClient } from "npm:@supabase/supabase-js@2";
const svc = createClient("http://127.0.0.1:54321", Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

const muckrockUuid = "11111111-1111-1111-1111-111111111111";
const { data, error } = await svc.auth.admin.createUser({
  id: muckrockUuid,
  email: "preflight@example.test",
  email_confirm: true,
  user_metadata: { muckrock_subject: muckrockUuid, muckrock_username: "preflight" },
});
if (error) throw error;
if (data.user?.id !== muckrockUuid) throw new Error(`id mismatch: ${data.user?.id}`);
console.log("ok: id preserved");
await svc.auth.admin.deleteUser(muckrockUuid);
```

**Pass:** prints `ok: id preserved`.
**Fail:** Supabase generated a new UUID — stop; need to raise this with Supabase before the window.

#### Preflight 2 — Custom OIDC discovery + end-to-end login

On a throwaway dev Supabase project (NOT `gfmdziplticfoakhrfpt`):

- Configure Custom OIDC provider `muckrock` in Dashboard → Authentication → Providers → Custom OIDC:
  - Issuer URL: `https://accounts.muckrock.com/openid`
  - Client ID: `879742`
  - Client Secret: *(from cojournalist/.env)*
  - Scopes: `openid profile uuid organizations email preferences`
  - Attribute mapping: `email → email`, `uuid → user_metadata.muckrock_subject`
- Ask MuckRock to temporarily register the dev project's callback URI, OR register it yourself if Tom's account has permission. Usually a quick Slack message to their admin.
- Manually navigate to the `/authorize` URL in a browser
- Sign in with Tom's own MuckRock account
- Verify the redirect lands with an access token, and `supabase.auth.getUser(token)` returns `{ user: { id: <tom's muckrock uuid>, email: ..., user_metadata: { muckrock_subject: ... } } }`

**Pass:** logs in, UUID matches Tom's MuckRock UUID (which must be pre-seeded first via admin.createUser).
**Fail:** Likely scope config or attribute mapping — iterate until green. The dev project is throwaway, so failures here are cheap.

#### Preflight 2.5 — MuckRock UUID enumeration (all 68 existing users)

**Added 2026-04-21 from migration audit.** The migration script's Phase 0 (`phase0Users` in `scripts/migrate/main.ts:118-198`) resolves each DynamoDB `PROFILE` UUID to an email by calling MuckRock's `/openid/users/{uuid}/` endpoint. If MuckRock returns 404 for a UUID (user deleted / suspended / data drift / permissions mismatch on the OAuth client), the script logs to stderr and silently skips that user — and **every downstream phase then drops every dependent record** (scouts, runs, units, promises, post_snapshots, seen_records, credits, org membership). The audit's T2 live run observed zero MuckRock warnings across 5 sampled UUIDs combined with zero downstream inserts, which is consistent with either (a) all lookups succeeded but fell through a different skip path, or (b) all lookups 404'd silently. The distinction matters enormously for the cutover bar — case (b) means the entire migration is a no-op and users log in to empty accounts.

Before scheduling the window, enumerate all existing DynamoDB PROFILE UUIDs against MuckRock and prove every UUID resolves to an email.

```bash
# From the repo root, against live prod creds
cd scripts/migrate
set -a; source ../../.env; set +a

deno run --allow-env --allow-net - <<'TS'
import { MuckrockClient } from "./lib/muckrock.ts";
import { DynamoDBClient, ScanCommand } from "npm:@aws-sdk/client-dynamodb@3.658.1";
import { unmarshall } from "npm:@aws-sdk/util-dynamodb@3.658.1";

const ddb = new DynamoDBClient({
  region: Deno.env.get("AWS_REGION") ?? "eu-central-1",
  credentials: {
    accessKeyId: Deno.env.get("AWS_ACCESS_KEY_ID")!,
    secretAccessKey: Deno.env.get("AWS_SECRET_ACCESS_KEY")!,
  },
});
const mr = new MuckrockClient(
  Deno.env.get("MUCKROCK_CLIENT_ID")!,
  Deno.env.get("MUCKROCK_CLIENT_SECRET")!,
);

const uuids: string[] = [];
let lastKey;
do {
  const r = await ddb.send(new ScanCommand({
    TableName: "scraping-jobs",
    FilterExpression: "SK = :sk",
    ExpressionAttributeValues: { ":sk": { S: "PROFILE" } },
    ProjectionExpression: "PK",
    ExclusiveStartKey: lastKey,
  }));
  for (const it of r.Items ?? []) {
    const pk = unmarshall(it).PK as string;
    uuids.push(pk.startsWith("USER#") ? pk.slice(5) : pk);
  }
  lastKey = r.LastEvaluatedKey;
} while (lastKey);

console.log(`Total PROFILE UUIDs: ${uuids.length}`);

let ok = 0, notFound = 0, noEmail = 0, otherErr = 0;
const failures: { uuid: string; reason: string }[] = [];
for (const uuid of uuids) {
  try {
    const u = await mr.getUser(uuid);
    if (!u) { notFound += 1; failures.push({ uuid, reason: "404" }); continue; }
    if (!u.email) { noEmail += 1; failures.push({ uuid, reason: "no email field" }); continue; }
    ok += 1;
  } catch (e) {
    otherErr += 1;
    failures.push({ uuid, reason: (e as Error).message });
  }
}
console.log(`resolved OK: ${ok}`);
console.log(`404 (not found): ${notFound}`);
console.log(`200 but no email: ${noEmail}`);
console.log(`other errors: ${otherErr}`);
if (failures.length) {
  console.log("\nFailures:");
  for (const f of failures) console.log(`  ${f.uuid}  ${f.reason}`);
}
TS
```

**Pass:** `resolved OK` equals total PROFILE count; `404` + `no email` + `other errors` all zero.

**Fail — `404` > 0:** these UUIDs no longer exist in MuckRock. Options:
1. Ask MuckRock admin to confirm whether the UUIDs were deleted/merged and whether archives exist (some may be data-migration artifacts from MuckRock's own past cutovers).
2. For truly-gone UUIDs, decide per-user: skip (their DynamoDB data migrates to an orphan with no auth) or hard-delete from DynamoDB before the window. Either way, document the decision — skipping produces ghost scouts, deleting loses historical data.

**Fail — `no email field` > 0:** the MuckRock userinfo response is missing `email`. Either a scope issue (confirm the OAuth client has `email` scope — check via `curl https://accounts.muckrock.com/.well-known/openid-configuration` and a test token introspection) or account-level (user removed their email in MuckRock). Contact MuckRock admin with the list.

**Fail — `other errors` > 0:** likely rate-limit or transport issue. Re-run with a 500ms sleep between calls: wrap the `mr.getUser(uuid)` line with `await new Promise(r => setTimeout(r, 500));`. If still failing, inspect `lib/muckrock.ts` for token-refresh bugs.

Only schedule the window when this preflight returns zero failures **or** every failing UUID has a documented resolution (skip / delete / wait-on-MuckRock-admin).

#### Preflight 3 — data migration dry-run against prod DynamoDB

```bash
cd scripts/migrate
AWS_ACCESS_KEY_ID=<read-only> AWS_SECRET_ACCESS_KEY=<...> AWS_REGION=eu-central-1 \
DYNAMODB_TABLE=cojournalist \
DYNAMODB_UNITS_TABLE=information-units \
SUPABASE_URL=<throwaway dev Supabase> \
SUPABASE_SERVICE_ROLE_KEY=<throwaway> \
MUCKROCK_CLIENT_ID=879742 \
MUCKROCK_CLIENT_SECRET=<...> \
DRY_RUN=false \
LIMIT_USERS=3 \
deno task cutover
```

Expected per-phase counters: `{read: N, inserted: N, skipped: 0, failed: 0}`. Sample one user, confirm their scouts + last run + 5 recent units look right in the Supabase table editor.

**Pass:** 3 users migrated cleanly, relationships intact, no failures logged.
**Fail:** inspect the log, fix the script, re-run. Don't proceed to preflight 4 until this is green.

#### Preflight 4 — frontend works against dev Supabase end to end

Point the already-merged frontend `VITE_API_URL` + `VITE_SUPABASE_URL` at the throwaway dev Supabase. Sign in as Tom (via the preflight-2 OIDC setup), confirm:

- `/workspace` loads
- Scout list shows the scouts that got migrated in preflight 3
- Clicking a scout opens unit details
- Triggering a scout run queues a scout_run and returns 202
- Signing out + back in preserves access

**Pass:** behaves exactly like production, just against the dev Supabase.
**Fail:** frontend-code issue; fix before scheduling the window.

#### Preflight sign-off

Only schedule the window when all 4 preflights are documented green. Tom posts in Slack: "Preflights 1–4 green on <date>, scheduling window for <target date>".

---

## The 4-hour window (suggested: Monday 09:00–13:00 UTC)

### T+0:00 — Take-down (≤5 min)

- Deploy maintenance page at `cojournalist.ai` (Render static override OR DNS flip)
- Pause AWS EventBridge schedulers:
  ```bash
  aws scheduler list-schedules --max-results 200 --output json \
    | jq -r '.Schedules[].Name' \
    | while read n; do aws scheduler update-schedule --name "$n" --state DISABLED ...; done
  ```
- Slack announce: "maintenance window started"

### T+0:05 — DynamoDB final snapshot (≤10 min, runs async)

```bash
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:eu-central-1:<acct>:table/cojournalist \
  --s3-bucket <backup bucket> \
  --s3-prefix cojournalist-final-pre-supabase \
  --export-format DYNAMODB_JSON
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:eu-central-1:<acct>:table/information-units \
  --s3-bucket <backup bucket> \
  --s3-prefix cojournalist-units-final-pre-supabase \
  --export-format DYNAMODB_JSON
```

Continue with the next steps while the exports run; wait for `Status=COMPLETED` before running the migration script.

### T+0:15 — Pre-seed Supabase Auth users (≤5 min)

Pre-create every existing MuckRock user so their `auth.users.id` matches the DynamoDB partition key. Script (runs from `scripts/migrate/`):

```bash
DRY_RUN=false PRESEED_ONLY=true deno task cutover
```

The migration script has a `PRESEED_ONLY` mode (to add if not present — trivial addition: run Phase 0 only). It scans DynamoDB `PROFILE` records, fetches email from MuckRock by UUID, and calls `supabase.auth.admin.createUser({ id, email, email_confirm: true, user_metadata })` idempotently. Re-runs are safe — existing users trigger an "already registered" error that the script swallows.

**Pass:** log shows `{read: 50, created: 50, already_existed: 0, failed: 0}` (or equivalent).

### T+0:20 — Enable MuckRock Custom OIDC on `cojournalist-prod` (≤10 min)

Dashboard → Authentication → Providers → **Custom OIDC** → Add:
- Provider name: `muckrock`
- Issuer URL: `https://accounts.muckrock.com/openid`
- Client ID: `879742`
- Client Secret: *(from `vault.decrypted_secrets` or the Dashboard Secrets panel)*
- Scopes: `openid profile uuid organizations email preferences`
- Attribute mapping:
  - `email` → `email`
  - `uuid` → `user_metadata.muckrock_subject`

Save. Confirm via a quick test login in an incognito window — you should land back on `cojournalist.ai/auth/callback` with a token, and your UUID should equal your pre-seeded row.

### T+0:30 — Full data migration (15–30 min)

```bash
cd scripts/migrate
AWS_ACCESS_KEY_ID=<read-only> AWS_SECRET_ACCESS_KEY=<...> AWS_REGION=eu-central-1 \
DYNAMODB_TABLE=cojournalist \
DYNAMODB_UNITS_TABLE=information-units \
SUPABASE_URL=https://gfmdziplticfoakhrfpt.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=<...> \
MUCKROCK_CLIENT_ID=879742 \
MUCKROCK_CLIENT_SECRET=<...> \
DRY_RUN=false \
deno task cutover 2>&1 | tee /tmp/cutover-$(date +%Y%m%d-%H%M).log
```

Per-phase summaries should show `failed: 0`. Any non-zero failure — STOP and inspect.

### T+1:00 — Verify migration (≤10 min)

```bash
cd scripts/migrate && deno task verify
```

Plus manual spot-check: sign in as Tom and 2 other users (or have a beta tester sign in); confirm their scouts + units look right.

### T+1:15 — Promote cutover frontend (≤15 min)

Either flip Render's active deploy to the pre-reviewed cutover PR, or trigger a fresh build from the PR branch. Confirm on `cojournalist.ai`:

- Landing page loads
- Sign-in button redirects to MuckRock → back through Supabase → lands on `/workspace`
- Scout list populates
- Triggering a run creates a scout_run and completes end-to-end

### T+1:30 — Smoke test (≤20 min)

Run `bash scripts/e2e-smoke.sh` with Tom's real JWT:

```bash
SUPABASE_URL=https://gfmdziplticfoakhrfpt.supabase.co \
USER_JWT=<Tom's JWT from browser devtools> \
bash scripts/e2e-smoke.sh
```

Expected: 12/12 checks pass. If any fail, diagnose before reopening the site.

### T+1:50 — Reopen (≤5 min)

- Remove maintenance page
- Announce completion: "coJournalist v2 is live"
- Monitor for 30 min before declaring the window closed

### T+2:20 → T+4:00 — Buffer

Unexpected issues get up to 1h 40min of extra time. If everything is quiet at T+2:30, close the window early.

---

## Rollback

| Stage reached | Action | Time budget |
|---|---|---|
| Pre-migration | Reopen site, re-enable EventBridge schedulers. Nothing changed. | 5 min |
| Migration mid-run | Run `docs/migration-rollback.sql` (TRUNCATE all public tables, keep auth.users). Re-run preseed if needed. Reopen FastAPI auth path via a revert deploy on Render. | 20 min |
| Frontend deployed, issues in live flow | Revert Render frontend deploy to pre-cutover tag; revert Supabase Auth changes (disable Custom OIDC provider). Users hit FastAPI auth again. | 25 min |
| Post-reopen, discovered within 24h | AWS Lambda + DynamoDB still running (unscheduled but warm). Re-enable schedulers, revert frontend, call cutover failed. | 30 min |

**Total rollback budget:** 30 min. AWS infrastructure stays warm for 30 days post-cutover as safety net.

`docs/migration-rollback.sql`:

```sql
-- Empty all v2 tables so the migration can be re-run from scratch.
-- Keeps auth.users intact — those rows are pre-seeded and safe.
TRUNCATE unit_entities, entities, reflections, information_units,
         raw_captures, civic_extraction_queue, apify_run_queue,
         promises, post_snapshots, seen_records, execution_records,
         scout_runs, scouts, ingests, project_members, projects,
         user_preferences
RESTART IDENTITY CASCADE;
```

Review and commit this file to the repo before the window.

---

## Post-window (first 72h)

- Monitor Supabase Edge Function logs for auth errors, Firecrawl/Gemini failures, cron job misses
- Keep AWS Lambda + DynamoDB running but schedulers DISABLED. Cold-standby for rollback
- Ask MuckRock to remove the old redirect URI after 7 days of observed stability

## 30-day sunset

- Stop FastAPI on Render (or keep if the admin dashboard is still needed and has been ported)
- S3 Glacier the DynamoDB exports
- Drop DynamoDB tables
- Close the AWS IAM keys used for the migration script

---

## Open questions (decide before scheduling the window)

1. **Frontend redirect target after OIDC login.** Plan assumes `https://cojournalist.ai/auth/callback` — a static SvelteKit route that extracts the token from the hash and stores it via `supabase.auth.setSession`. Confirm this route exists in the cutover PR.
2. **Supabase project URL in browser during redirect.** Users briefly see `gfmdziplticfoakhrfpt.supabase.co` in the URL bar. Optional polish: set up a CNAME like `auth.cojournalist.ai` pointing at the Supabase endpoint. Supabase Pro plan supports this; check current tier.
3. **Email confirmation toggle.** Supabase Custom OIDC doesn't need email confirmation (OIDC userinfo is trusted). Dashboard → Authentication → Email → "Confirm email" should be OFF for the cutover, then optionally re-enabled afterward for email/password signup paths.
4. **Refresh-token rotation.** Default in Supabase is enabled (rotated on use, 10s reuse interval). That's what we want. Verify in Dashboard → Authentication → Configuration.

Resolve all 4 before scheduling the window.

---

## Work that must land before the window

1. **Pre-work v2-followups complete** — new workspace UI, `cojo` binary releases, MCP OAuth server all live and pointed at pre-cutover FastAPI. See `docs/v2-followups.md`.
2. **MuckRock confirms new redirect URI is registered** — email chain saved.
3. **Preflights 1–4 documented green** — logs or screenshots in a Slack thread.
4. **Cutover PR merged to `main`** — includes the auth-supabase frontend store wired as primary, FastAPI `/auth/*` route deletions, `migration-rollback.sql`, and any `PRESEED_ONLY` additions to the migration script.
5. **Final dry-run on a throwaway dev Supabase** 24–48h before the window, with all four preflight steps repeated end-to-end.
