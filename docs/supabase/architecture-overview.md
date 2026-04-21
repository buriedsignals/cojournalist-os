# Architecture overview

High-level map of the Supabase layer. If you're new to this codebase, start here.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            BROWSER (SvelteKit SPA)                         │
│                                                                            │
│  authStore ── Supabase JS client ── JWT(auth.users.id)                     │
│       │                                                                    │
│       ▼                                                                    │
│   fetch(/functions/v1/*, Authorization: Bearer <jwt>)                      │
└────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE EDGE FUNCTIONS                            │
│                                                                            │
│   user          scouts       units         civic-execute   billing-webhook │
│   projects      ingest       units-search  civic-extract   apify-callback  │
│   reflections   entities     main          social-kickoff  apify-reconcile │
│   execute-scout scout-beat-execute         scout-web-execute               │
│   scout-health-monitor    openapi-spec     mcp-server      export-claude   │
│                                                                            │
│   • requireUser()   → user-scoped client (RLS applies)                     │
│   • service-role    → full access, bypasses RLS                            │
│   • requireServiceKey() → X-Service-Key for function-to-function calls     │
└────────────────────────────────────────────────────────────────────────────┘
                                       │
                       ┌───────────────┴────────────────┐
                       ▼                                ▼
┌──────────────────────────────────┐   ┌───────────────────────────────────┐
│      POSTGRES (Supabase DB)      │   │         pg_cron (in-DB)           │
│                                  │   │                                   │
│  Tables:                         │   │  Every 2m:  civic-extract-worker  │
│   scouts, scout_runs             │   │  Every 10m: apify-reconcile,      │
│   information_units, entities    │   │             civic_queue_failsafe  │
│   credit_accounts, usage_records │   │  Every 15m: apify-mark-timeouts   │
│   orgs, org_members              │   │  Daily 00:10: reset-expired-      │
│   projects, project_members      │   │               credits             │
│   user_preferences               │   │  Daily 03:00–03:30 UTC (stagger): │
│   civic_extraction_queue         │   │               cleanup-* jobs      │
│   apify_run_queue                │   │  Monday 09:00: scout-health-      │
│   raw_captures, ingests          │   │                monitor            │
│   mcp_oauth_clients / _codes     │   │                                   │
│                                  │   │  Jobs HTTP-POST to Edge Functions │
│  RPCs (SECURITY DEFINER):        │   │  via pg_net + vault secrets.      │
│   decrement_credits              │   └───────────────────────────────────┘
│   topup_team_credits             │                   │
│   schedule_scout                 │                   ▼
│   trigger_scout_run              │     ┌─────────────────────────────────┐
│   semantic_search_units          │     │   vault.decrypted_secrets       │
│   check_unit_dedup               │     │   (project_url, service_role_   │
│   increment_scout_failures       │     │    key) used by SECURITY        │
│   merge_entities                 │     │   DEFINER RPCs only             │
│   claim_civic_queue_item         │     └─────────────────────────────────┘
│   + cleanup_* (11 functions)     │
│                                  │
│  Extensions:                     │
│   vector (pgvector, 1536-dim)    │
│   pg_cron, pg_net, pg_trgm       │
│                                  │
│  RLS enabled on every app table. │
└──────────────────────────────────┘
                  ▲
                  │ MuckRock HMAC webhook (billing-webhook)
                  │ Apify webhook (apify-callback)
                  │
┌─────────────────┴───────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                              │
│   MuckRock (identity + billing)   Apify (social scraping)               │
│   Firecrawl (web scrape)          Gemini (LLM + embeddings)             │
│   OpenRouter (fallback LLM)       Resend (email)                        │
│   MapTiler (geocoding)                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Who calls what

| Caller | Auth | Reaches |
|---|---|---|
| Browser (SvelteKit) | Supabase JWT | Edge Functions over HTTPS |
| Edge Function user-path | user JWT → user-scoped client | Postgres via PostgREST, RLS applies |
| Edge Function admin-path | service-role client | Postgres, RLS bypassed |
| Edge Function → Edge Function | `X-Service-Key` header | Mostly `scout-*-execute` functions |
| pg_cron → Edge Function | service-role key from vault | Any Edge Function (via `pg_net.http_post`) |
| MuckRock webhook | HMAC-SHA256 signature | `billing-webhook` only |
| Apify webhook | `x-internal-key` header | `apify-callback` only |

## Where state lives

| What | Where |
|---|---|
| User identity | `auth.users` (Supabase-managed) |
| User preferences + tier pointer | `user_preferences` |
| Current credit balance | `credit_accounts` (user row or team `org_id` row) |
| Scout configuration | `scouts` |
| Scout execution history | `scout_runs` + `execution_records` |
| Extracted facts | `information_units` (+ `unit_entities` junction) |
| Entity canonical records | `entities` |
| Civic promise tracking | `promises` |
| Social post baselines | `post_snapshots` |
| Worker queues | `civic_extraction_queue`, `apify_run_queue` |
| Raw scraped content | `raw_captures` |
| Audit trail (90-day) | `usage_records` |
| MCP OAuth flow state | `mcp_oauth_clients` + `mcp_oauth_codes` |

## What isn't in Supabase

- **Frontend build artefacts** — SvelteKit SPA is hosted separately (Render static).
- **LLM prompts & schemas** — live in Edge Function source.
- **Secrets** (API keys for Gemini/Apify/etc.) — Edge Function env vars (Dashboard → Edge Functions → Secrets). The only secrets *inside* the DB are the two vault entries `project_url` + `service_role_key` used by SECURITY DEFINER RPCs.
- **Render cron schedules** — none; all scheduling is pg_cron.
- **AWS anything** — legacy, decommissioning per `docs/v2-migration-runbook.md`.

## Migration philosophy

- Every schema change is a new migration file. **Never edit a shipped migration.**
- File names are zero-padded sequential (`000NN_name.sql`); pick the next number.
- Keep migrations small and single-concern. Tables in one file, indexes next, RLS after, RPCs later.
- RLS goes up at the same time as tables; if you `CREATE TABLE` without RLS in the same migration batch, you've shipped a leak.
- SECURITY DEFINER RPCs always `SET search_path = public` and always `REVOKE EXECUTE FROM PUBLIC, anon, authenticated` on anything mutating.
- Cron jobs that invoke Edge Functions pull the URL + service role key from `vault.decrypted_secrets` — never hard-code.

## Further reading

- Per-system docs in this directory — see [README](./README.md) index.
- `docs/auth-db-migration.md` — the cutover plan that brought MuckRock users into `auth.users`.
- `docs/v2-migration-runbook.md` — operational playbook.
