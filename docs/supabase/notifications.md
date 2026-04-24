# Scout notifications

Per-run email alerts sent via Resend when a scout produces new, non-duplicate
content. The shared renderer now follows the editorial design system in
`DESIGN.md`: warm cream paper background, sharp edges, hairline borders,
mono uppercase labels, serif headlines, and per-scout identity carried only
through accent treatment.

## Where the code lives

| File | Purpose |
|---|---|
| `supabase/functions/_shared/notifications.ts` | Shared helper — 6 public entry points, editorial HTML renderer, Resend transport, retry logic |
| `supabase/functions/_shared/email_translations.ts` | 12-language copy table (`en`, `no`, `de`, `fr`, `es`, `it`, `pt`, `nl`, `sv`, `da`, `fi`, `pl`) |
| `supabase/functions/_shared/notifications.test.ts` | Deno unit tests covering the editorial shell, i18n fallback, markdown escape, article grouping, digest/health coverage |
| `supabase/functions/notifications-benchmark/index.ts` | Edge-Function-based preview runner |
| `scripts/notifications-benchmark.ts` | Local preview runner (bypasses Supabase, uses Resend directly) |

## Public entry points

Every worker calls one of these at the end of a successful run. All
**never throw** — Resend failures are logged as `notifications:send_failed`
and the worker carries on.

| Function | Hook location | Variant | Key elements |
|---|---|---|---|
| `sendPageScoutAlert` | `scout-web-execute/index.ts` | `page` | Monitoring URL panel, criteria panel, matched-content card, page-scout cue |
| `sendBeatAlert` | `scout-beat-execute/index.ts` | `beat` | Location/topic eyebrow, findings block, Top Stories cards, optional government section |
| `sendCivicAlert` | `civic-extract-worker/index.ts` | `civic` | Promise markdown rendered into editorial findings block, civic cue |
| `sendSocialAlert` | `apify-callback/index.ts` | `social` | `@handle on PLATFORM` eyebrow, profile panel, new-post cards, optional caution block |
| `sendCivicPromiseDigest` | `promise-digest/index.ts` | `digest` | Civic digest shell for due-today promises across scouts |
| `sendScoutDeactivated` | `scout-health-monitor/index.ts` | `health` | Scout health metadata panels, paused summary, health-specific copy |

Legacy "Smart Scout" is now "Beat Scout" everywhere. The old `pulse`
storage value was migrated; `beat` is the canonical scout type in the
live contract.

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
      │     — structured editorial sections:
      │       eyebrow/context row, metadata panels, findings block,
      │       cards, optional secondary/caution sections
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

## Renderer contract

`buildBaseHtml(...)` is the shared shell. It expects a `variant` plus
structured content inputs rather than prebuilt HTML strings.

- `variant`: `page | beat | civic | social | digest | health`
- `metadataPanels`: bordered key/value panels for URLs, criteria, profile links, health details
- `cueText`: scout-specific italic verification cue
- `secondarySection`: optional follow-on section for grouped supporting material
- `cautionSection`: optional bordered block for removed posts / warnings

The HTML must stay fully inline-styled. Email clients strip `<style>` tags and
do not reliably support external assets or CSS custom properties.

## Testing

```bash
# Pure-function tests — no network.
deno test --allow-env supabase/functions/_shared/notifications.test.ts
```

Covers: editorial-shell invariants, all 12 locales × 6 email types,
markdown-to-HTML escape safety, article-grouping edge cases, inline-CSS
requirements, and Unicode round-trip.

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
