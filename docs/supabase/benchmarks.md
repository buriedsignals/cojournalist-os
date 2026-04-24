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
`tom@buriedsignals.com`. The Page and Social benchmarks still resolve this
to an existing `auth.users.id` via the admin API. Beat and Civic create a
temporary benchmark user in-script instead.

## The scripts

| Script | Benchmarks | Legacy Python equivalent |
|---|---|---|
| `scripts/benchmark-web.ts` | Page Scout (web) across blocked/normal URLs | `benchmark_web.py` |
| `scripts/benchmark-beat.ts` | Beat Scout discovery-path health benchmark (preview + execution) | historical `benchmark_pulse.py` |
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
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts --scout-id <existing-beat-scout-uuid>
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts --timeout-min 8
```

Default run uses a temporary user plus five fixed canaries:
- location-only
- topic-only
- topic+country
- topic+city
- second topic+country canary

Each canary must pass both:
- preview search (`beat-search`) returns `> 0` articles
- scheduled execution returns `> 0` units / `articles_count`

The script retries a canary once when the live environment returns a likely
transient failure (`preview returned zero articles`, `execution returned zero units`,
or run polling timeout). Semantic drift failures are not retried.

`--scout-id` clones an existing Beat scout configuration onto the temporary
benchmark user and replays it without mutating the original scout.

### Civic Scout

```bash
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts --url https://council.example/minutes
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts --max-drain 20
```

Three-phase:
- `civic/discover` selects the best listing page candidate for the supplied URL
- `civic/test` verifies the selected page resolves downstream meeting documents
- `civic-execute` enqueues docs, then the script loops `civic-extract-worker`
  to drain `civic_extraction_queue` until idle (or `--max-drain` reached)

The script creates its own temporary benchmark user, so it does not depend
on a pre-seeded auth user in the target project.

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
- `benchmark-beat.ts` seeds credits on its temporary user, so it does not
  consume a real user's balance during the manual weekly health check.
