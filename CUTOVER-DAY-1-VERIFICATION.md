# Cutover Day-N Follow-Ups

The 2026-04-22 cutover landed (PR #71 + finish-the-cutover sweep PR #72).
The v2 architecture is live in production. This doc is the **single source
of truth** for every remaining task — anything not listed here is either
done or out of scope.

Items use the original ticket numbers from the pre-cutover follow-up
list where applicable so cross-references stay stable.

---

## Tom's manual actions remaining

Code-side work is done for #20, #21, #5, #23 as of 2026-04-22. These
console-only actions unblock real user flows:

- **MuckRock admin — NO action required.** The `muckrock_proxy.py`
  router on Render forwards both MuckRock-registered URLs to the right
  Supabase EFs byte-for-byte:
    `POST https://www.cojournalist.ai/api/auth/webhook` → `billing-webhook`
    `GET  https://cojournalist.ai/api/auth/callback`   → `auth-muckrock/callback`
  (The OAuth callback is registered on the **apex** `cojournalist.ai`,
  not `www` — MuckRock rejects `www` with "Redirect URI Error". See
  `docs/muckrock/oauth-integration.md` for the byte-exact-match rationale.)
- **Supabase EF secrets — DONE 2026-04-22:** `SESSION_SECRET`,
  `PUBLIC_APP_URL=https://www.cojournalist.ai`,
  `APP_POST_LOGIN_REDIRECT=https://www.cojournalist.ai/`,
  `MCP_STATE_SECRET`, and
  `MUCKROCK_CALLBACK_URL=https://cojournalist.ai/api/auth/callback`
  **(apex — critical for MuckRock byte-exact match on both the
  authorize call and the token-exchange call)** all set on the
  `auth-muckrock` EF. `EMAIL_ALLOWLIST` optional.

---

## Critical path — finish the migration

### #18 (3) — AWS wipe

**Status:** Lambda functions, EventBridge schedules, DynamoDB tables,
and the API Gateway are still alive in `eu-central-1`. Production
traffic stopped routing to them on 2026-04-22; they're idle but billing.

**Pre-wipe gate:** keep DynamoDB backups for **30 days post-cutover**
(until 2026-05-22). Most recent backup: `pre-cutover-20260421-2137`.

**Sequence (Tom executes manually — destructive, prod, irreversible):**

1. **Disable EventBridge schedules first.** `aws scheduler list-schedules`
   then disable each. Stops Lambda invocations cleanly.
2. **Wait 7 days** for any straggler invocations / debugging window.
3. **Delete Lambda functions:**
   ```bash
   for fn in $(aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `coj-`) || starts_with(FunctionName, `cojournalist-`)].FunctionName' --output text); do
     aws lambda delete-function --function-name "$fn"
   done
   ```
4. **Delete API Gateway:** `aws apigatewayv2 list-apis` → identify
   `coj-*` APIs → `aws apigatewayv2 delete-api --api-id <id>`.
5. **Delete IAM roles + policies** scoped to the Lambdas
   (`lambda-execution-coj-*`).
6. **Delete EventBridge schedule group** (`coj-scouts` or similar).
7. **Wait until 2026-05-22**, then delete DynamoDB tables + backups.
8. **Render env-var cleanup:** drop `AWS_API_BASE_URL`,
   `INTERNAL_SERVICE_KEY` if no live caller (verify via grep first),
   and any `AWS_*` credentials previously used by the FastAPI scheduler.
9. **Repo cleanup:** `rm -rf aws/`; update `Dockerfile` if it copied
   AWS configs; update `backend/CLAUDE.md` (still pre-cutover); delete
   or banner-mark `docs/architecture/aws-architecture.md` and
   `docs/architecture/records-and-deduplication.md` (still describe the
   dead architecture as authoritative).

---

## macOS release binaries — attach when Apple notary recovers

**Status as of 2026-04-22:** Linux binaries for `cojo` and `cojo-mcp`
ship on every tag via `cli-release.yml` / `mcp-release.yml`. macOS
binaries are **best-effort** (`continue-on-error: true`,
`required: false`) because Apple's notary service had an extended
"stuck In Progress" period during our first releases that burned
~1,650 billable GitHub Actions minutes before we caught it (macOS
runners bill at 10× Linux).

**Current release state:** the latest `cli-v*` / `mcp-v*` tag
publishes Linux binaries immediately. macOS binaries are missing from
the release page until Apple's notary clears.

**To attach macOS binaries later (once Apple is healthy):**

1. Check https://developer.apple.com/system-status/ — "Developer ID
   Notary Service" should be green AND recent submissions should be
   clearing in < 5 min (not the "stuck In Progress" pattern).
2. From GitHub Actions UI → `CLI Release` or `MCP Bridge Release` →
   select the tagged run → **Re-run failed jobs**. Only the macOS
   legs rerun; Linux binaries already in the release remain untouched.
3. The `release` job reruns too and `files: dist/*` + softprops-
   action-gh-release upload the new macOS binaries alongside the
   existing Linux ones. Tag + release URL stay the same.

**Guardrails in place (don't remove — see `cli/CLAUDE.md` § "Release
cost controls"):**
- `timeout-minutes: 25` on the Notarize step + 20-min internal poll
  loop → no more runaway macOS jobs.
- macOS legs `continue-on-error: true` → they never block Linux.
- Notarization uses explicit submit + UUID poll (not `--wait`) — see
  electron/notarize#179.

---

## Tracked but lower priority

### #11 — Adapter pattern review

**Status:** `docs/oss/adapter-pattern.md` describes a port/adapter
design. After the EF migration, half the adapters may be obsolete
(anything that abstracted DynamoDB vs Supabase).

**What to do:** audit `backend/app/adapters/` — keep only what's still
load-bearing post-cutover. Update the doc if the model changed.

**Status note:** cleanup-adjacent; explicitly dropped from the
2026-04-22 cutover-finish session.

### #16 — General code cleanup (`/cleanup` skill)

**Status:** lots of orphaned code surfaced by the cutover. Run the
`/cleanup` skill across the repo.

**Specifically:**
- `backend/app/services/` orphans listed in
  `docs/architecture/api-surface-audit.md`: `pulse_orchestrator.py`,
  `social_orchestrator.py`, `civic_orchestrator.py`,
  `post_snapshot_service.py`, `execute_pipeline.py`. No live
  importers after PR #72.
- `frontend/src/lib/utils/` — any helpers only used by deleted AI Select.
- `aws/` — anything left after the EventBridge teardown (item #18).

**Status note:** explicitly dropped from the 2026-04-22 cutover-finish session.

### #19 — Manual delete `export-select` EF

**Status:** Orphaned in Supabase since PR #71. No caller hits it.

**What to do:** delete from the Supabase dashboard when convenient
(GUI action; no code change).

---

## Documentation drift (sweep when adjacent work happens)

### Frontend AWS-era references

Cosmetic but stale:
- `frontend/src/lib/components/panels/ScoutsPanel.svelte:99` — comment
  reads "Fetch all scouts from AWS"; now it's Supabase.
- `frontend/src/lib/types.ts:50` — `ActiveJobLastRun` documented as
  "AWS Active Jobs types".
- `frontend/CLAUDE.md` may still mention AWS in places.

**Bundle with #18 (AWS wipe) — same scope.**

### `backend/CLAUDE.md` is pre-cutover

Still describes `/api/scouts/*`, `/api/pulse/*` etc. as live with
Lambda triggers. Replace with the post-cutover surface (auth broker +
feedback + `/api/v1` + adapter notes).

**Bundle with #18.**

### Historical architecture docs

- `docs/architecture/aws-architecture.md` — describes Lambda +
  EventBridge + DynamoDB as authoritative. Add a "historical / removed
  YYYY-MM-DD" banner OR delete entirely after item #18 lands.
- `docs/architecture/records-and-deduplication.md` — same; describes
  DynamoDB record types. Banner or delete.

**Bundle with #18.**

### Render env vars audit

Listed in `docs/architecture/api-surface-audit.md` but not actioned.
Once item #18 ships, drop `AWS_API_BASE_URL` and audit
`INTERNAL_SERVICE_KEY` callers via grep — likely now safe to remove.

**Bundle with #18.**

---

## Verification & validation gaps (no action required, just notes)

### #17 — Smart-Alfred verification pass

**Status:** deferred. Read-only verification of the cloud architecture
post-cutover.

**Recommended prompt for a standalone session:**

> Verify Supabase config (RLS policies, EF deployment status, pg_cron
> jobs), Render envVars (still-required vs prunable per
> `docs/architecture/api-surface-audit.md`), and AWS resources (alive
> but soon-to-be-deleted per item #18). Output: punchlist or "all wired"
> confirmation. Read-only.

Run this *after* item #18 is at least started so the AWS state is
known.

### #13 / #14 — OSS mirror local validation

**Status:** `scripts/strip-oss.sh` uses GNU `sed -i` syntax that fails
on macOS BSD sed. CI runs Linux so the existing `oss-mirror-check`
job exercises it on every push. **No fix needed** unless local
developer ergonomics become a frequent pain — at which point switch
to portable sed (e.g. `sed -i.bak ... && rm *.bak` or use `perl -i`).

### Email notifications path (was #22)

**Status:** verified live during the cutover (PRs #70/71). Bundle into
any future EF observability pass if/when notifications need work.

### Linear feedback widget (was #9)

**Status:** verified live; `feedback.py` router preserved in PR #72.
No follow-up unless feedback router is later deleted.

### Newsletter signup (was #10)

**Status:** verified live; wired to `supabase/functions/newsletter-subscribe/`.
No follow-up.

### Login dual-path (was #12)

**Status:** verified live; both MuckRock OAuth and email/password
render correctly. Toggle controlled by `PUBLIC_MUCKROCK_ENABLED`.
No follow-up.

---

## Reference

- Post-cutover endpoint inventory: `docs/architecture/api-surface-audit.md`
- Supabase architecture: `docs/supabase/architecture-overview.md`
- CLI auth: `cli/CLAUDE.md` "Auth precedence"
- Cutover-finish PR: #72
