# Edge Functions reference

Every Supabase Edge Function. Grouped by system. For each: method/path, auth model, request/response, downstream dependencies.

## User & auth

### `user` — `/user/*`
| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/user/me` | GET | user JWT | Profile + tier + credits + team |
| `/user/preferences` | GET | user JWT | `user_preferences` row |
| `/user/preferences` | PATCH | user JWT | Update timezone/language/overflow JSONB |
| `/user/onboarding-complete` | POST | user JWT | Flip `onboarding_completed = TRUE` |

Reads `user_preferences`, `credit_accounts`, `orgs`, `org_members`. See [auth-users.md](./auth-users.md) for the `/me` response shape.

### `billing-webhook` — `/billing-webhook`
| Method | Auth | Purpose |
|---|---|---|
| POST | HMAC-SHA256 signature | MuckRock webhook dispatcher |

Verifies HMAC over `timestamp + type + uuids.join('')` with `MUCKROCK_CLIENT_SECRET`; rejects stale timestamps. Dispatches to:
- `type=user` → `applyUserEvent(userinfo)`
- `type=organization individual=true` → `applyIndividualOrgChange(org)`
- `type=organization` with `cojournalist-team` entitlement → `applyTeamOrgTopup(org, ent)` → `topup_team_credits` RPC
- `type=organization` without team entitlement → `cancelTeamOrg(uuid)`

Shared helpers: `_shared/muckrock.ts`, `_shared/entitlements.ts`. See [credits-entitlements.md](./credits-entitlements.md).

## Scouts

### `scouts` — `/scouts/*`
CRUD + scheduling management for scouts.

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/scouts` | GET | user JWT | List |
| `/scouts` | POST | user JWT | Create; calls `schedule_scout` RPC if `is_active` |
| `/scouts/:id` | GET/PATCH/DELETE | user JWT | Read/update/delete; PATCH can flip `is_active` (re-/unschedule) |
| `/scouts/:id/run` | POST | user JWT | Manual trigger — calls `trigger_scout_run` RPC |

### `execute-scout` — `/execute-scout`
Thin dispatcher. Called by pg_cron and `trigger_scout_run`. Loads scout, routes to `scout-web-execute` / `scout-beat-execute` / `social-kickoff` / `civic-execute` based on `scout.type`. Service-role Bearer auth.

### `scout-web-execute` — Page Scout runner (+ Phase B subpage-follow)
Service-role auth. Decrements credits (1, `website_extraction`), Firecrawl
scrape branched on `scout.provider` (firecrawl changeTracking vs
firecrawl_plain + SHA-256 hash dedup, baseline verified by double-probe),
optional per-article Gemini extraction via `_shared/atomic_extract.ts` when
`criteria` is set — 5W1H prompt, forced `preferred_language`, max 8 units.
Within-run paraphrase dedup via `_shared/dedup.ts` (cosine threshold 0.75)
before the shared `upsertCanonicalUnit(...)` helper. The helper calls the
atomic `upsert_canonical_unit` RPC, which handles same-scout exact checks,
cross-scout exact checks, then semantic canonical matching.
Sends `sendPageScoutAlert` on new non-duplicate units. On error:
`incrementAndMaybeNotify` + `refund_credits` RPC.

**Phase B — subpage-follow (listing pages only).** When extraction returns
`isListingPage: true`, or the index has a strong deterministic listing signal
(the index URL is not article-like and exposes at least 3 safe same-host
article candidates), the pipeline enters Phase B: extracts links from the
index's `rawHtml` via `extractLinksFromHtml`, filters via
`filterSubpageUrls()` (`_shared/subpage-filter.ts` — strict child paths plus
clear same-host article routes such as `...-ld.NNN`, numeric IDs, and
`.html/.php/.aspx`; traversal/static/cross-host/local URLs rejected),
deduplicates against `information_units.source_url` for this scout, caps at
10 fresh URLs, scrapes each with a stagger delay, and runs
`extractAtomicUnits()` on each article body. Single-hop invariant: subpages
that themselves return `isListingPage: true` are skipped, not recursed. No new
DB column; seen-URL set derived from existing units.

**Step 6b algorithm:**
```
1. links      ← extractLinksFromHtml(rawHtml, scout.url)    # host-lock
2. candidates ← filterSubpageUrls(links, scout.url)          # child paths + safe same-host articles
3. seen       ← SELECT DISTINCT source_url FROM information_units WHERE scout_id = $1
4. fresh      ← (candidates − seen)[0 : 10]                  # CAP = 10
5. for url in fresh (sequential, staggered):
     md ← firecrawlScrape(url)
     result ← extractAtomicUnits(md, { sourceUrl: url })
     if result.isListingPage: skip          # single-hop, no recursion
     else: insert units
```

**Cost:** worst case 1 + 10 = 11 Firecrawl scrapes per run (~15–25s). Steady
state after initial seed: 0–2 new subpages per run. Files:
`supabase/functions/scout-web-execute/index.ts` (wiring),
`supabase/functions/_shared/subpage-filter.ts` (tested pure helper),
`scripts/benchmark-subpage-follow.ts` (end-to-end benchmark).

### `scout-beat-execute` — Beat Scout runner
`X-Service-Key` or service-role auth. Decrements credits (7, `beat`).
Branches on `priority_sources`:
- **Manual path** (non-empty): parallel scrape of up to 20 URLs
  (concurrency 5), per-source Gemini extraction (1–3 units per article,
  forced target language), within-run paraphrase dedup +
  `upsertCanonicalUnit(...)`, `sendBeatAlert` with plain bulleted summary.
- **Discovery path** (empty): full 8-stage pipeline via
  `_shared/beat_pipeline.ts` — LLM query gen (multilingual, category-
  aware) → Firecrawl search fan-out → date filter + undated cap →
  tourism pre-filter (niche+location+news only) → embedding dedup with
  rarity scoring + `+8` local-language bonus → cluster filter (niche only)
  → AI relevance filter → per-article extraction. Optional parallel
  `government` category fan-out when criteria+location are both set;
  two-section email via `sendBeatAlert({articles, govArticles, govSummary})`
  with LLM-composed `generateBeatSummary` per section.

On empty pipeline yield OR error: refunds the 7 credits via `refund_credits`
(matches legacy no-charge-on-no-op semantics).

### `social-kickoff` — Social Scout async start
Service-role auth. Decrements credits (per platform). Validates platform
against `APIFY_ACTORS` map (instagram, x, facebook, tiktok) before
decrementing. Reuses the dispatcher-supplied `run_id` when present (no
orphan `scout_runs` rows). Registers the Apify webhook via a base64-encoded
JSON query parameter (`?webhooks=<urlencode(base64(...))>`), not the JSON
body (which Apify silently ignores). On Apify network/non-2xx failure:
`markQueueFailed` now also issues a `refund_credits` call so users don't
pay for runs Apify never executed.

### `civic-execute` — Civic Scout runner
`X-Service-Key` auth. Enforces `regularity ∈ {weekly, monthly}` (rejects
daily with 400 — backs up the same check in `scouts` Edge Function's zod
refinement). Decrements credits (`civic` = 10), Firecrawl change-tracking
per `tracked_urls`, parses markdown for PDF + civic-document links using
the 40-term multilingual keyword list in `MEETING_KEYWORDS`
(DE/FR/EN/IT/ES/PT/NL/PL). Caps enqueues at `MAX_DOCS_PER_RUN = 2`.
Refunds the 10 credits when `queuedCount === 0` at end-of-run (all pages
unchanged or URLs already seen) OR on error. On error:
`incrementAndMaybeNotify` fires the shared deactivation email when the
3-strike threshold trips.

### `civic-extract-worker` — Civic queue worker
Service-role auth. Cron-driven every 2 minutes. Claims one row via
`claim_civic_queue_item` RPC (includes `scout_run_id`). Gemini extraction
with a language-forced system prompt (matches the scout's
`preferred_language`) and a 5W1H civic system instruction. Criteria is
passed as filter data to the user prompt (not instructions). Inserts
`raw_captures`, canonical `information_units`, `unit_occurrences`, and
`promises`, then fires `sendCivicAlert` only when a new canonical promise
unit is created. Failed processing attempts 1-2 are reset to `pending`; attempt
3 becomes terminal `failed`. Linked `scout_runs` are marked error only after
all pending/processing work for that run is settled and a row reaches terminal
failure.

### `civic-test` — Dev tooling
Runs a single civic extraction without scheduling for iterating on prompts/schemas.

### `apify-callback` — Apify webhook receiver
`x-internal-key` header auth. Receives `ACTOR.RUN.SUCCEEDED`/`FAILED`/`TIMED_OUT`; fetches posts from dataset; diffs against `post_snapshots`; inserts units for new posts.
New social units route through the same canonical `upsertCanonicalUnit(...)`
helper as web/beat/civic/manual-ingest. Exact matches can merge across scout
types; semantic matching does not cross the `social` / `non-social` boundary.

### `apify-reconcile` — Lost-webhook catcher
Service-role auth. Cron-driven every 10 minutes. Polls Apify for `running` rows > 10 minutes old; processes terminal ones like `apify-callback` would.

### `scout-health-monitor` — Weekly digest
Service-role auth. Cron-driven Monday 09:00 UTC. Finds auto-paused scouts
(`is_active=FALSE`, `consecutive_failures >= 3`), groups by owner, and emails
each owner a Resend digest so they can re-enable. Respects per-user opt-in
via `user_preferences.health_notifications_enabled` (default `TRUE`, toggled
in the Preferences modal).

### `notifications-benchmark` — Dev/QA email preview
Service-role auth. Not scheduled. Renders and Resend-sends one sample email
per scout type (page / beat / civic / social) to a target address. Used to
visually confirm HTML templates across Gmail / Apple Mail / Outlook before
real traffic flows.

```bash
curl -X POST "$SUPABASE_URL/functions/v1/notifications-benchmark" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"tom@buriedsignals.com","language":"en"}'
```

A local-only variant that bypasses Supabase entirely lives at
`scripts/notifications-benchmark.ts` — runs the same shared template code
and POSTs directly to Resend. Useful during iteration:

```bash
set -a; source .env; set +a
deno run --allow-env --allow-net --allow-read=. \
  scripts/notifications-benchmark.ts tom@buriedsignals.com en 3
# Sends runs \u00d7 4 emails (page + beat + civic + social).
```

### `scout-templates` — Template starter
User JWT. Returns pre-configured scout templates for the UI "quickstart" flow.

### `manage-schedule` — Cron-wrapper helper
Service-role auth. Exposes `schedule_cron_job` / `unschedule_cron_job` RPCs via HTTP for agents that need to schedule/unschedule scouts without direct DB access.

## Units, entities, projects

### `units` — `/units/*`
CRUD over canonical `information_units`. User JWT + RLS. Project and scout
filters resolve through `unit_occurrences`.

### `units-search` — `/units-search`
Text query → Gemini embedding → `semantic_search_units` RPC.

### `entities` — `/entities/*`
CRUD over `entities` + `POST /entities/:id/merge` (wraps `merge_entities` RPC).

### `reflections` — `/reflections/*`
CRUD + `/reflections/search` (wraps `semantic_search_reflections`).

### `ingest` — `/ingest`
User JWT. Accepts `{kind, source_url?, content?, project_id}`. Queues an
`ingests` row, fetches content (firecrawl for URL, direct for text, pdf parse
for PDF), inserts `raw_captures`, extracts via Gemini, and routes every unit
through `upsertCanonicalUnit(...)` with `source_type='manual_ingest'`.

### `projects` — `/projects/*`
CRUD over `projects` + `project_members`. Default "Inbox" project is protected from deletion.

## Search

## MCP / API

### `mcp-server` — `/.well-known/*`, `/register`, `/authorize`, `/token`, JSON-RPC root
OAuth 2.0 + PKCE flow + MCP protocol endpoint. Hosted production proxies this
function at `/mcp`; raw Supabase installs use
`/functions/v1/mcp-server`. See [mcp-oauth.md](./mcp-oauth.md).

### `openapi-spec` — `/openapi-spec`
Public (no auth). Returns JSON OpenAPI 3.0 spec for the coJournalist API (scouts/units/projects endpoints). Generated from hand-maintained `spec.json`.

### `main` — `/main`
Legacy placeholder; the default `/` routing target. Returns a health-check response.

## Shared helpers

`supabase/functions/_shared/`:

| File | Exports |
|---|---|
| `cors.ts` | `handleCors()`, `makeCorsHeaders()`, `corsHeaders` |
| `responses.ts` | `jsonOk()`, `jsonError()`, `jsonPaginated()`, `jsonFromError()` |
| `errors.ts` | `ApiError`, `AuthError`, `ValidationError`, `NotFoundError` |
| `auth.ts` | `requireUser(req)`, `requireServiceKey(req)`, `AuthedUser` |
| `supabase.ts` | `getServiceClient()`, `getUserClient(bearerToken)` |
| `log.ts` | `logEvent({level, fn, event, user_id?, msg?, ...})` |
| `firecrawl.ts` | `firecrawlScrape()`, `firecrawlChangeTrackingScrape()`, `doubleProbe()`, `firecrawlSearch()`, `firecrawlMap()` |
| `gemini.ts` | `geminiEmbed()`, `geminiExtract(prompt, schema, { systemInstruction? })` |
| `atomic_extract.ts` | `extractAtomicUnits()`, `publishedDateFromScrape()`, `languageName()` — ports prod's `atomic_unit_service._extract_atomic_units` (5W1H + forced language) |
| `notifications.ts` | `sendPageScoutAlert`, `sendBeatAlert`, `sendCivicAlert`, `sendSocialAlert`, `buildBaseHtml`, `escapeHtml`, `markdownToHtml`, `groupFactsBySource`, `renderArticleCards`, `buildProfileUrl`, `resolveUserContext` |
| `email_translations.ts` | `EMAIL_STRINGS`, `getString(key, language, params?)`, `SUPPORTED_LANGUAGES` |
| `db.ts` | Query helpers (batch inserts, upserts) |
| `credits.ts` | `CREDIT_COSTS`, `decrementOrThrow`, `InsufficientCreditsError`, `insufficientCreditsResponse`, `SOCIAL_MONITORING_KEYS`, `EXTRACTION_KEYS`, `getSocialMonitoringCost`, `getExtractionCost`, `calculateMonitoringCost` |
| `muckrock.ts` | `MuckrockClient` with `fetchUserData`, `fetchOrgData` |
| `entitlements.ts` | `resolveTier`, `applyAdminOverride`, `applyUserEvent`, `applyIndividualOrgChange`, `applyTeamOrgTopup`, `cancelTeamOrg`, `upsertUserCredits`, `upsertUserPreferences`, `seedTeamOrg` |
| `subpage-filter.ts` | `filterSubpageUrls(links, indexUrl)` — pure Phase B filter: path-prefix under index, safe same-host article routes, traversal/static block, domain validator. Tested in `_shared/subpage_filter_test.ts`. |

## Auth models

| Auth kind | Header | Verification | Used by |
|---|---|---|---|
| User JWT | `Authorization: Bearer <jwt>` | `requireUser(req)` — `client.auth.getUser()` | Frontend-facing functions |
| Service-role | `Authorization: Bearer <service_role_key>` | Exact-match compare to `SUPABASE_SERVICE_ROLE_KEY` | Function-to-function, cron → edge function |
| X-Service-Key | `X-Service-Key: <INTERNAL_SERVICE_KEY>` | Exact-match compare | Function-to-function (legacy but still in use) |
| MuckRock HMAC | signed body | SHA-256(timestamp+type+uuids, MUCKROCK_CLIENT_SECRET) | `billing-webhook` only |
| Apify internal key | `x-internal-key: <INTERNAL_SERVICE_KEY>` | Exact-match compare | `apify-callback` only |
| API key | `Authorization: Bearer cj_<key>` | DB lookup | Agent-facing REST and MCP endpoints |
| None (public) | — | — | `openapi-spec`, `/.well-known/*`, `main` |

## Deployment

All functions ship as a single bundle:

```bash
supabase functions deploy --no-verify-jwt \
  auth-muckrock-callback billing-webhook user \
  scouts execute-scout scout-web-execute scout-beat-execute \
  social-kickoff apify-callback apify-reconcile scout-health-monitor \
  notifications-benchmark civic-execute civic-extract-worker civic-test \
  units units-search entities reflections \
  ingest projects \
  mcp-server openapi-spec manage-schedule scout-templates main
```

`--no-verify-jwt` disables Supabase's automatic JWT check so each function can implement its own auth model (many use service-role or HMAC instead of user JWT).

## Environment variables

Set in Dashboard → Edge Functions → Secrets:

| Var | Consumer | Purpose |
|---|---|---|
| `SUPABASE_URL` | all | Auto-injected |
| `SUPABASE_SERVICE_ROLE_KEY` | all | Auto-injected |
| `SUPABASE_ANON_KEY` | user/auth funcs | Auto-injected |
| `INTERNAL_SERVICE_KEY` | service-to-service | Rotate on cutover; do NOT reuse Render's value |
| `GEMINI_API_KEY` | scout-*, ingest, units-search | Google AI Studio |
| `OPENROUTER_API_KEY` | scout-* (fallback) | Fallback LLM |
| `FIRECRAWL_API_KEY` | scout-*, civic-extract-worker, ingest | Scraping |
| `APIFY_API_TOKEN` | social-kickoff, apify-reconcile | Social scraping |
| `RESEND_API_KEY` | scout-health-monitor, scout-web-execute, scout-beat-execute, civic-extract-worker, apify-callback, notifications-benchmark | Per-run scout alerts + weekly health digest + benchmark email preview |
| `MUCKROCK_CLIENT_ID` | billing-webhook, user | MuckRock API |
| `MUCKROCK_CLIENT_SECRET` | billing-webhook | HMAC verification |
| `ADMIN_EMAILS` | entitlements | Comma-separated; auto-upgrade to pro |
| `LLM_MODEL` | scout-* | Default `gemini-2.5-flash-lite` |

## See also

- `docs/supabase/architecture-overview.md` — who-calls-what diagram
- `docs/supabase/vault-secrets.md` — `vault.decrypted_secrets` used by pg_cron HTTP jobs
- Each system doc covers its Edge Functions in depth.
