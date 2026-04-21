# Scout benchmarks

Port of `backend/scripts/benchmark_*.py` to the Supabase world. Each script
creates an ephemeral scout owned by a test user, invokes the real Edge
Functions end-to-end, inspects `scout_runs` / queue rows / units, and
cleans up. All live under `scripts/` and speak HTTP to the linked
Supabase project — no Python, no FastAPI.

## Prerequisites

```bash
# SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY must be available. Default:
# load them from the project .env.
set -a; source .env; set +a
```

Optional: `BENCH_OWNER_EMAIL=<you@example.com>` — defaults to
`tom@buriedsignals.com`. The script resolves this to an `auth.users.id`
via the admin API; the user must already exist.

## The scripts

| Script | Benchmarks | Legacy Python equivalent |
|---|---|---|
| `scripts/benchmark-web.ts` | Page Scout (web) across blocked/normal URLs | `benchmark_web.py` |
| `scripts/benchmark-beat.ts` | Beat Scout (pulse) across scenarios with priority sources | `benchmark_pulse.py` |
| `scripts/benchmark-civic.ts` | Civic Scout (civic-execute + civic-extract-worker drain) | `benchmark_civic.py` |
| `scripts/benchmark-social.ts` | Social Scout (social-kickoff → Apify → apify-callback) | `benchmark_social.py` |
| `scripts/notifications-benchmark.ts` | All 4 email templates to inbox (standalone, no Supabase needed) | — (new) |

### Page Scout

```bash
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-web.ts
```

Tests 3 URLs: blocked (nytimes.com), normal (neunkirch.ch), normal (politico.com).
Asserts `scout_runs.scraper_status` matches expectation per URL class.

### Beat Scout

```bash
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts           # quick (2 scenarios)
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts --full    # 4 scenarios
```

Scenarios cover location + topic, reliable + niche source modes, with
real priority sources.

### Civic Scout

```bash
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts --url https://council.example/minutes
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts --max-drain 20
```

Two-phase: `civic-execute` enqueues PDFs, then loops `civic-extract-worker`
to drain `civic_extraction_queue` until idle (or `--max-drain` reached).

### Social Scout

```bash
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-social.ts
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-social.ts \
  --platform x --handle SadiqKhan --mode summarize
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-social.ts \
  --platform instagram --handle natgeo --mode criteria \
  --criteria "wildlife, climate"
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-social.ts --no-wait
```

Kicks off Apify, polls `apify_run_queue` every 15s until terminal
(default timeout 10 min, override with `--timeout-min`). Use `--no-wait`
to return immediately and inspect rows manually later.

### Notifications benchmark

**Local (no Supabase, uses RESEND_API_KEY from .env):**

```bash
deno run --allow-env --allow-net --allow-read=. \
  scripts/notifications-benchmark.ts tom@buriedsignals.com en 3
# runs * 4 emails: Page, Beat, Civic, Social
```

**Deployed (requires `notifications-benchmark` Edge Function):**

```bash
curl -X POST "$SUPABASE_URL/functions/v1/notifications-benchmark" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"tom@buriedsignals.com","language":"en"}'
```

## Shared helpers

`scripts/_bench_shared.ts` — `getCtx()`, `svcFetch()`, `pgInsert()`,
`pgSelectOne()`, `pgDelete()`, `hr()`, `ok()`, `fail()`, `dur()`. Zero
runtime deps beyond Deno's std lib — all PostgREST + Edge Function fetches.

## Notes

- Scouts are created with `is_active=false` and `schedule_cron` set so the
  `chk_active_has_schedule` constraint passes. The schedule is never armed
  because the scout is deleted (or orphaned, for social) at the end of the run.
- Social scouts are NOT auto-deleted if we're still polling the Apify queue
  at teardown — otherwise the callback would fail. Use `--no-wait` for a
  clean exit and inspect/clean up later.
- Credit decrement is live — each run charges the owner's real credit
  account. Use a test user with plenty of credits, or bump via
  `docs/supabase/credits-entitlements.md`.
