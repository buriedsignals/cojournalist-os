# Scout notifications

Per-run email alerts sent via Resend when a scout produces new, non-duplicate
content. Ported from the legacy FastAPI `notification_service.py`; templates,
colors, and copy are preserved for visual parity.

## Where the code lives

| File | Purpose |
|---|---|
| `supabase/functions/_shared/notifications.ts` | Shared helper — 4 public entry points, HTML templates, Resend transport, retry logic |
| `supabase/functions/_shared/email_translations.ts` | 12-language copy table (`en`, `no`, `de`, `fr`, `es`, `it`, `pt`, `nl`, `sv`, `da`, `fi`, `pl`) |
| `supabase/functions/_shared/notifications.test.ts` | 39 Deno unit tests covering templates, i18n fallback, markdown escape, article grouping |
| `supabase/functions/notifications-benchmark/index.ts` | Edge-Function-based preview runner |
| `scripts/notifications-benchmark.ts` | Local preview runner (bypasses Supabase, uses Resend directly) |

## Public entry points

Every worker calls one of these at the end of a successful run. All four
**never throw** — Resend failures are logged as `notifications:send_failed`
and the worker carries on.

| Function | Hook location | Theme | Key elements |
|---|---|---|---|
| `sendPageScoutAlert` | `scout-web-execute/index.ts` | Dark header `#1a1a2e`, blue accent `#2563eb` | Monitoring URL box, Criteria box, matched-content card, page-scout cue |
| `sendBeatAlert` | `scout-beat-execute/index.ts` | Purple gradient `#7c3aed → #6d28d9` | Location/topic context, Top Stories grouped by source, pulse cue |
| `sendCivicAlert` | `civic-extract-worker/index.ts` | Amber gradient `#d97706 → #b45309` | Markdown promises list with `[title](source)` links, civic cue |
| `sendSocialAlert` | `apify-callback/index.ts` | Rose gradient `#e11d48 → #be123c` | `@handle on PLATFORM` context, new-posts cards, optional Removed Posts section |

Legacy "Smart Scout" is now "Beat Scout" everywhere — DB `scout.type` enum
stays `pulse`, only user-facing labels changed.

## Control flow

```
worker success path
      │
      ▼
sendXAlert(svc, { userId, scoutId, runId, ... })
      │
      ├─ resolveUserContext(svc, userId)
      │     ├─ svc.auth.admin.getUserById(userId)    → email
      │     └─ user_preferences                      → language
      │
      ├─ build HTML via buildBaseHtml(...)
      │     — inline CSS only (Gmail/Outlook strip <style>)
      │     — localized disclaimer + scout-specific cue
      │     — per-type gradient, accent, article cards
      │
      ├─ sendWithRetry(RESEND_API_KEY, to, subject, html)
      │     — POST https://api.resend.com/emails
      │     — 3 attempts, exp backoff (1s, 2s), 4xx fast-fail
      │
      └─ on HTTP 200:
             UPDATE scout_runs
             SET notification_sent = true
             WHERE id = runId
```

Key semantics:

- **Mark-after-send.** `notification_sent=true` flips only after Resend 200,
  so UI never lies. Cost: small double-send risk on worker retry — acceptable.
- **No refunds for mail failures.** Credits pay for scouting work; Resend is
  best-effort.
- **Async workers, linked runs.** `civic-execute` and `social-kickoff` persist
  `scout_run_id` on their queue rows (migration `00029`) so the downstream
  worker/callback can flip `notification_sent` on the correct row.

## i18n

`user_preferences.preferred_language` drives the locale. Fallback chain:

```
EMAIL_STRINGS[lang][key]  ?? EMAIL_STRINGS.en[key]  ?? key
```

Unknown languages fall back to English; unknown keys return the key name
(loud but non-fatal).

Phase 1 renders article *titles* in the source language — legacy
`translate_titles_batch` (OpenRouter dependency) is not ported.

## Health-monitor opt-in

`scout-health-monitor` respects the new `user_preferences.health_notifications_enabled`
column (default `TRUE`, migration `00028`). Users can flip it from the
Preferences modal under the "Notifications" section. Missing rows fall back
to the DB default, so new users are opted in until they say otherwise.

## Testing

```bash
# 39 pure-function tests — no network.
deno test --allow-env supabase/functions/_shared/notifications.test.ts
```

Covers: template snapshots per type, all 12 locales × 4 types smoke-rendered,
markdown-to-HTML escape safety, article-grouping edge cases, inline-CSS
invariants, Unicode round-trip.

## Visual QA — send the 4 templates to your inbox

**Option A — local Deno script (fastest, no deploy):**

```bash
set -a; source .env; set +a
deno run --allow-env --allow-net --allow-read=. \
  scripts/notifications-benchmark.ts tom@buriedsignals.com en 3
# Sends runs × 4 emails. Subjects tagged [BENCHMARK #1..#N].
```

**Option B — deployed Edge Function (production-path check):**

```bash
curl -X POST "$SUPABASE_URL/functions/v1/notifications-benchmark" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"tom@buriedsignals.com","language":"en"}'
```

Both render the *same* shared template code. Use A for iteration, B for
end-to-end confirmation after deploy.

## Resend configuration

- **Endpoint:** `https://api.resend.com/emails`
- **From:** `coJournalist <info@cojournalist.ai>`
- **Reply-to:** `info@cojournalist.ai`
- **Auth:** `Authorization: Bearer ${RESEND_API_KEY}`
- **Retry:** 3 attempts max, exponential backoff (1s, 2s); 4xx fast-fails.
