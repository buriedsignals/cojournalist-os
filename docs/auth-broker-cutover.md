# Plan 01 — Auth Migration (FastAPI Broker + Supabase generateLink)

**Strategy:** Keep FastAPI on Render with ONLY auth routes (login, callback, webhook). Delete every other router. FastAPI does the MuckRock OAuth handshake (unchanged), then calls `supabase.auth.admin.createUser` + `supabase.auth.admin.generateLink({type: 'magiclink'})`, then 302s the browser to the `action_link`. Supabase issues a JWT + refresh token pair. Frontend reads hash tokens, calls `setSession()`. MuckRock redirect URI stays `https://cojournalist.ai/api/auth/callback` — zero MuckRock coordination. OSS mirror deletes FastAPI entirely; uses Supabase email/password auth directly.

---

## (a) Prerequisites — before the cutover window

1. **Supabase project `gfmdziplticfoakhrfpt` configuration**
   - Dashboard → Authentication → URL Configuration → Redirect URLs: add `https://cojournalist.ai/auth/callback` and `http://localhost:5173/auth/callback`.
   - Dashboard → Authentication → Providers: Email provider enabled, email confirmation OFF (or pass `email_confirm: true` on every `admin.createUser` call).
   - Dashboard → Authentication → Rate limits: confirm "Magic link requests" is at/above 30/sec (for preseed). Bump for the window if needed.
   - Capture: service_role key, anon key, JWT secret, project URL → Render env vars (scratchpad).

2. **Local/dev verification (preflight)** — ship-blocker
   - Run `supabase start` locally.
   - Throwaway script: `admin.createUser({id: <fixed-uuid>, email, email_confirm: true})`, then `admin.generateLink({type: 'magiclink', email, options: {redirectTo: 'http://localhost:5173/auth/callback'}})`. Verify `properties.action_link` returned. Open it. Verify lands at `/auth/callback#access_token=...`. Verify `supabase.auth.getUser(token).id` matches the fixed UUID.
   - If UUID preservation fails: **stop**, escalate to Supabase support, do not proceed.
   - Full frontend locally against `supabase start` through the auth-supabase store; confirm the hash-fragment read works.

3. **Data-migration dry-run against prod DynamoDB** — phase 0 already seeds auth.users. Dry-run with `LIMIT_USERS=3` against a throwaway dev Supabase. All phases `failed=0`.

4. **FastAPI Render service snapshot** — capture current env var list + current image SHA. Rollback = Render dashboard "Rollback to previous deploy".

5. **Branch hygiene** — create `auth-broker-cutover` branch off `main`. All PRs land on this branch; `main` merges in one go after the window.

---

## (b) Ordered PRs

### PR 1 — Pre-seed path in migration script (PARALLEL with PR 2, PR 3)

- Extend `scripts/migrate/main.ts` with `PRESEED_ONLY=true` env var → runs only phase 0 then exits.
- Add rate limiter: sleep ~35ms between `admin.createUser` calls (stays under 30/sec).
- Reuse existing `MuckrockClient`, `makeClient`, `scanByPrefix`, `getServiceClient`.
- Update `scripts/migrate/README.md` with one-paragraph invocation docs.

**Acceptance:** `PRESEED_ONLY=true DRY_RUN=false deno task cutover` completes in <5s for 50 users; `select count(*) from auth.users` = 50.

### PR 2 — FastAPI auth.py rewrite + webhook rewrite (PARALLEL)

Files:
- `backend/app/config.py` — add `supabase_url`, `supabase_service_role_key`, `supabase_jwt_secret`, `supabase_post_login_redirect` settings (all from env).
- `backend/app/routers/auth.py`:
  - Delete `UserService`, `SessionService` imports + globals.
  - Add lazy `_supabase_admin` global via `create_client(settings.supabase_url, settings.supabase_service_role_key)`.
  - `login`: unchanged (state creation, redirect to MuckRock).
  - `oauth_callback`: preserve state verification, code exchange, userinfo fetch, email allowlist. Replace DynamoDB-create + cookie-set with:
    1. `supabase_admin.auth.admin.create_user({"id": muckrock_uuid, "email": email, "email_confirm": True, "user_metadata": {...}})` — catch "already exists"/"already been registered"/"duplicate" substrings, log DEBUG, continue.
    2. `supabase_admin.auth.admin.generate_link({"type": "magiclink", "email": email, "options": {"redirect_to": settings.supabase_post_login_redirect}})`. Extract `properties.action_link`.
    3. `RedirectResponse(url=action_link, status_code=302)`. No cookie.
  - Delete `/me`, `/status`, `/logout`.
  - `handle_webhook`: preserve HMAC verification unchanged. Rewrite event processing to use supabase-py:
    - Event `user`: `supabase_admin.auth.admin.update_user_by_id(uuid, {"user_metadata": ...})` + upsert `user_preferences` via PostgREST.
    - Event `organization` individual: upsert `user_preferences` or dedicated tier table.
    - Event `organization` team: TODO comment — teams may not yet be modeled in v2 schema; log+skip for now, document in PR.

- `backend/app/dependencies/auth.py` — drop session-cookie branch. `get_current_user` always expects `Authorization: Bearer <supabase_jwt>`, validates via `supabase-py`'s `get_user(token)`.

**DO NOT delete yet** in this PR: `user_service.py`, `session_service.py`, other routers. They stay importable but unmounted. PR 4 deletes them after Render deploy is stable (1-change-per-step rule, simpler rollback).

**Acceptance:** `cd backend && pytest tests/` passes; `uvicorn app.main:app --reload` starts cleanly; manual probe: `/api/auth/login` → MuckRock → login with preseeded test account → `/auth/callback#access_token=...` → `getUser(token)` resolves to correct UUID.

### PR 3 — Frontend auth store swap (PARALLEL)

Files:
- `frontend/src/lib/stores/auth.ts` — re-export from `auth-supabase` unconditionally. Delete `auth-muckrock.ts` (SaaS and OSS now share auth-supabase — simplifies strip-oss.sh too).
- `frontend/src/lib/stores/auth-supabase.ts`:
  - Drop `/api/auth/me` fetch on init. Read user metadata from `session.user.user_metadata`.
  - `login()`: `window.location.href = '/api/auth/login'` (FastAPI broker still handles MuckRock handshake).
- **New:** `frontend/src/routes/auth/callback/+page.svelte`
  - `onMount`: parse `window.location.hash`, extract `access_token` + `refresh_token` via URLSearchParams.
  - `supabase.auth.setSession({access_token, refresh_token})`.
  - On error: show "Login failed, please try again", link to `/login`.
  - On success: `history.replaceState({}, '', '/workspace')`, `goto('/workspace')`.
  - MUST be inside `if (browser)` / `onMount` — no SSR exposure.
- `frontend/src/lib/api-client.ts` — already reads `authStore.getToken()` → Bearer. Change `$lib/config/api`'s `VITE_API_URL` resolution: `https://gfmdziplticfoakhrfpt.supabase.co/functions/v1` in production; `http://localhost:54321/functions/v1` in dev. Remove `credentials: 'include'` from fetch calls.
- `frontend/src/routes/login/+page.svelte` — delete `handleSupabaseAuth` code path + signup-mode toggle (those are OSS-only). Keep `auth.login()` button → FastAPI broker. Logic drops from ~100 lines to ~15.
- `frontend/src/routes/login-supabase/+page.svelte` — keep unchanged; becomes primary OSS login page via `strip-oss.sh`'s existing `mv` logic.
- `frontend/.env.example` / `.env.production` — document `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`, `VITE_API_URL`. Remove any `VITE_MUCKROCK_*`.

**Acceptance:** `cd frontend && npm run check && npm run build` passes. Local: sign in via FastAPI broker (pointed at dev Supabase) → redirect to `/auth/callback#...` → setSession → `/workspace`.

### PR 4 — FastAPI non-auth surface deletion (POST-CUTOVER, separate PR)

Only after Render deploy has been stable >60min with users logging in cleanly.

Files to delete:
- `backend/app/routers/`: scouts, pulse, social, civic, scraper, units, data_extractor, export, onboarding, user, v1, admin, license, threat_modeling/
- `backend/app/services/`: user_service, session_service, scout_service, pulse_orchestrator, social_orchestrator, civic_orchestrator, query_generator, openrouter, news_utils, notification_service, email_translations, embedding_utils, url_validator, execution_deduplication, atomic_unit_service, feed_search_service, schedule_service, seed_data_service, execute_pipeline, filter_prompts, post_snapshot_service, scout_runner, admin_report_service, api_key_service, export_generator, cron, locale_data, crypto, license_key_service
- **Keep:** `muckrock_client.py`, `http_client.py`
- `backend/app/adapters/`, `backend/app/workflows/`, `backend/app/ports/`, `backend/app/schemas/` (most), `backend/app/dependencies/providers.py`, `billing.py`

Files to edit:
- `backend/app/main.py` — delete all non-auth router imports + mounts. Delete `SPAStaticFiles` class + `FRONTEND_DIST` mount (frontend lives on Cloudflare/static hosting). Delete `has_users`. Keep `/api/health`, `/api/ready`.
- `backend/requirements.txt` — remove `boto3`, `asyncpg`, `numpy`, `stripe`, `langdetect`, `slowapi`, `resend`. Keep `fastapi`, `uvicorn`, `python-multipart`, `pydantic`, `pydantic-settings`, `PyJWT`, `httpx`, `python-dotenv`, `supabase`.
- `backend/app/config.py` — delete all AWS, DynamoDB, EventBridge, Firecrawl, Apify, OpenRouter, Gemini, Resend, Stripe, credit settings. Keep MuckRock, Supabase, email allowlist, environment.

**Why separate from cutover PR:** if something breaks during window, `git revert` on ONE PR rolls back FastAPI cleanly.

### PR 5 — Render environment variables

Add to Render web service: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.
Keep: `MUCKROCK_*`, `SESSION_SECRET`, `EMAIL_ALLOWLIST`, `ADMIN_EMAILS`, `ENVIRONMENT`, `OAUTH_REDIRECT_BASE`.
Remove (after PR 4 merges): `AWS_*`, `DYNAMODB_*`, `EVENTBRIDGE_*`, `FIRECRAWL_API_KEY`, `APIFY_API_TOKEN`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `RESEND_API_KEY`, `STRIPE_*`, `INTERNAL_SERVICE_KEY`, `LLM_MODEL`, `DEFAULT_USER_CREDITS`.

Frontend (Cloudflare Pages): `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`, `VITE_API_URL`, `PUBLIC_MAPTILER_API_KEY`.

### PR 6 — OSS mirror strip update

- `scripts/strip-oss.sh`: prepend `rm -rf backend/` — supersedes per-file backend deletions. Remove `backend/app/main.py` sed edits (dir gone). Remove `auth.ts` rewrite (both SaaS and OSS share it after PR 3). Keep `login` / `login-supabase` swap. Add OSS-only Dockerfile handling.
- `docker-compose.yml` — remove `backend` service.
- New `Dockerfile.oss` (or strip-oss overwrites the root Dockerfile) — two-stage: Node build → nginx:alpine serving static SPA.
- `deploy/SETUP.md` — "Self-hosted auth uses Supabase directly; no FastAPI required."

**Acceptance:** `bash scripts/strip-oss.sh` in clean checkout; `cd frontend && npm run build` passes; OSS tree has no `backend/`; `docker-compose up` starts only frontend; `/login` shows email/password form.

### PR 7 — Smoke tests + docs

- `scripts/e2e-smoke.sh` — add auth-flow prelude: GET `/api/auth/login` returns 302 to `https://accounts.muckrock.com/openid/authorize...`. Don't attempt headless round-trip.
- `docs/auth-db-migration.md` — deprecate OIDC content; point at `docs/auth-broker-cutover.md`. Preserve reusable sections (preflights, rollback).
- Manual test checklist (in cutover issue):
  1. Incognito → `https://cojournalist.ai/login`.
  2. Click "Sign in via MuckRock".
  3. Sign in as Tom. Verify redirect ends at `/workspace` with no hash in URL bar.
  4. User menu shows correct email.
  5. Create Page Scout targeting `https://example.com`. Save.
  6. Run now. Wait 10s. Verify scout_run appears with `status=success`.
  7. Information unit appears in Feed.
  8. Sign out → `/login`. Sign in again → full flow → `/workspace`.

---

## (c) Cutover window sequence (T+0:00 → T+2:00)

| T | Step | Actor | Verify |
|---|---|---|---|
| 00:00 | Post maintenance banner (Cloudflare Worker or HTML redirect) | Ops | Banner loads |
| 00:02 | Snapshot DynamoDB: `aws dynamodb create-backup --table-name cojournalist --backup-name pre-cutover-<date>` + units table | Ops | Status=CREATING |
| 00:05 | Pause MuckRock webhook: add 503 short-circuit at top of `handle_webhook`, deploy | Eng | `curl /api/auth/webhook` → 503 |
| 00:08 | **Preseed auth.users**: `PRESEED_ONLY=true DRY_RUN=false deno task cutover` | Eng | Log: `created/confirmed N auth.users` with N≈50 |
| 00:12 | **Deploy FastAPI** with new `auth.py` (merge branch to main → Render auto-deploy) | Eng | Render deploy Live |
| 00:20 | **Deploy frontend** (merge → Cloudflare Pages build) | Eng | `/login` serves new bundle |
| 00:25 | **Full data migration**: `DRY_RUN=false deno task cutover` (15-25min) | Eng | All phases `failed=0` |
| 00:50 | Verify data integrity: `select count(*) from auth.users` = 50, scouts count matches SCRAPER# records, units count ±10% | Eng | Counts within tolerance |
| 01:00 | `bash scripts/e2e-smoke.sh` with Tom's JWT | Eng | Exit code 0 |
| 01:10 | Manual test checklist (8 steps) | Eng | All pass |
| 01:25 | Re-enable webhook (remove 503, redeploy) | Eng | Test POST → 200 |
| 01:30 | Remove maintenance banner; announce completion | Ops | Normal traffic |
| 01:35 | Monitor Render + Supabase auth logs for 25min | Eng | No error spikes |
| 02:00 | Window closes | — | — |

**Rollback (if 01:10 or 01:25 fails):**
1. Render → Rollback to previous deploy (auth.py reverts to DynamoDB, session cookies resume). ~90s.
2. Cloudflare Pages → rollback to previous frontend deploy. ~30s.
3. Un-pause webhook.
4. Supabase data stays (additive migration, no DDB deletes). Old flow works.

Total rollback: ~3min.

---

## (d) Post-cutover cleanup

- **T+24h:** if no issues, merge PR 4 (FastAPI non-auth deletion) → Render auto-deploys slimmed image. Verify `/api/auth/login` still 302s. Remove AWS env vars.
- **T+48h:** scale Render service to 1 instance (auth brokering is light; ~100 req/day).
- **T+7d:** manually fire `mirror-oss.yml` to ensure PR 6 changes land cleanly in OSS.
- **T+30d:** consider moving MuckRock OAuth handshake into Edge Functions (requires `auth.cojournalist.ai` CNAME + one-line MuckRock email). Out of scope for this migration.
- Docs: update `docs/auth-db-migration.md` as-built; add `docs/architecture/auth-broker.md` with flow diagram.

---

## (e) Risks + mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `generateLink` response shape in supabase-py 2.x differs from JS SDK | Medium | High | Test against local Supabase in PR 2; have fallback paths. |
| `admin.createUser` silently generates new UUID despite `id:` param | Low | Critical | Preflight 1 covers; dry-runs green. |
| Magic link single-use: client-side nav interrupts setSession → user stuck | Medium | Medium | `/auth/callback` catches errors, shows "Try again" link to `/login` restart. |
| Rate-limit on `generateLink` per-email | Low | Medium | Default 30/hr; fine for normal use. |
| MuckRock userinfo returns no email | Low | High | Redirect `/login?error=no_email`; alert. |
| Webhook lag during window | Medium | Low | Paused during window; MuckRock retries 3x. |
| Cross-site / SameSite issues on redirect round-trip | Low | Low | Using hash fragment, not cookies. |
| SvelteKit SSR tries setSession server-side | Medium | Medium | `onMount` + `if (browser)`; no `+page.ts` loader. |

---

## (f) Test strategy

**Automated (pre-window):** pytest, `npm run check && npm run build`, `npm test`, `deno task cutover DRY_RUN=true` on CI.
**Automated (during window):** `scripts/e2e-smoke.sh`, `curl /api/health` → 200.
**Manual (during window):** 8-step checklist in PR 7 (~10 min).
**Post-window monitoring (first 24h):** Sentry / console for `setSession` failures, FastAPI logs for `create_user` exceptions not matching "already exists", Supabase Dashboard → Logs → Auth for `magiclink.verify` failures.

---

## (g) Ordering

```
Prerequisites
   │
   ├── PR 1 (preseed)      ╮
   ├── PR 2 (auth.py)      ├── parallel subagents
   └── PR 3 (frontend)     ╯
          │
          ├── PR 5 (Render env added)
          ▼
    === CUTOVER WINDOW ===
          │
          ▼
    === POST-CUTOVER ===
          ├── PR 4 (FastAPI surface deletion)    ╮
          ├── PR 5 (env removed)                  ├── parallel
          ├── PR 6 (OSS mirror strip)             │
          └── PR 7 (smoke + docs)                 ╯
```

Subagents pre-window: Agent A → PR 1, Agent B → PR 2, Agent C → PR 3. Converge on `auth-broker-cutover` branch.
