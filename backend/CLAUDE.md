# Backend (FastAPI) — post-cutover residual

> **Post-cutover status (2026-04-22):** the v2 migration moved scout execution,
> search, social/civic orchestrators, scheduling, and scout CRUD into Supabase
> Edge Functions. This FastAPI service is now a **thin residual** that handles
> auth brokering, MuckRock OAuth proxying, the `/api/v1` public API for the
> `cojo` CLI, the Linear feedback widget, the admin dashboard, license keys,
> and a small set of legacy endpoints that haven't been migrated yet.
>
> For the authoritative live surface see `docs/architecture/api-surface-audit.md`.
> For Supabase Edge Functions see `docs/supabase/edge-functions.md`.

Python FastAPI backend hosted on Render at `https://www.cojournalist.ai/api/*`.

## Live routers (`backend/app/routers/*`)

| Router | Mount | Purpose | SaaS-only? |
|---|---|---|---|
| `muckrock_proxy.py` | `/api/auth/webhook`, `/api/auth/callback` | Byte-for-byte forwards to Supabase `auth-muckrock` / `billing-webhook` EFs (MuckRock-registered URLs). | Yes |
| `feedback.py` | `/api/feedback` | Linear support widget — POST creates Linear issues. | Yes |
| `license.py` | `/api/license/*` | License-key gating (OSS Sustainable Use License). | No |
| `onboarding.py` | `/api/onboarding/*` | Timezone/language/location bootstrap, tour-complete flag. | No |
| `user.py` | `/api/user/*` | User preferences, data export, GDPR account deletion. | No |
| `units.py` | `/api/units/*` | Legacy unit helpers still called by the SPA (being migrated to EFs). | No |
| `export.py` | `/api/export/*` | Article-draft export from units, CMS push. | No |
| `v1.py` | `/api/v1/*` | Public REST API (CLI auth via Bearer `cj_...` API key). | No |
| `threat_modeling/` | `/api/threat-modeling/*` | Internal threat-assessment dashboard. | Yes |

SaaS-only routers are stripped from the OSS mirror by `scripts/strip-oss.sh`.
When adding a SaaS-only router or service you MUST update `strip-oss.sh`.

## Live services (`backend/app/services/*`)

Kept because they back the residual routers above:

| Service | Used By |
|---|---|
| `api_key_service.py` | `v1.py` (cj_… API keys) |
| `crypto.py` | `api_key_service.py`, session tokens |
| `email_translations.py` | `notification_service.py` |
| `embedding_utils.py` | `execution_deduplication.py`, `feed_search_service.py` |
| `execution_deduplication.py` | — (used by legacy scout_service only) |
| `export_generator.py` | `routers/export.py` |
| `feed_search_service.py` | `routers/units.py`, `routers/v1.py` |
| `filter_prompts.py` | `news_utils.py`, `export_generator.py` |
| `http_client.py` | Shared connection pooling |
| `license_key_service.py` | `routers/license.py` |
| `locale_data.py` | `email_translations.py`, `onboarding.py` |
| `notification_service.py` | — (used by legacy scout_service only) |
| `openrouter.py` | `export_generator.py` |
| `schedule_service.py` | `routers/v1.py` scout list/CRUD |
| `seed_data_service.py` | `routers/onboarding.py` |
| `session_service.py` | Session cookie encode/decode |
| `url_validator.py` | `export_generator.py` CMS SSRF guard |
| `user_service.py` | `routers/user.py` |

`scout_service.py`, `news_utils.py`, `atomic_unit_service.py`,
`query_generator.py` are currently unreferenced after the `/scouts/{name}/run`
route was removed. They're still on disk; delete in a follow-up sweep once
confirmed unused via access logs.

## Adapters (`backend/app/adapters/supabase/*`)

Supabase is the only registered backend after the v2 cutover. The port/adapter
pattern is kept for DI and testability. Surviving adapters and their ports:

| Port | Adapter |
|---|---|
| `ScoutStoragePort` | `scout_storage.py` |
| `ExecutionStoragePort` | `execution_storage.py` |
| `RunStoragePort` | `run_storage.py` |
| `UnitStoragePort` | `unit_storage.py` |
| `UserStoragePort` | `user_storage.py` |
| `SchedulerPort` | `scheduler.py` |
| `AuthPort` | `auth.py` |
| `BillingPort` | `billing.py` (no-op) |

Retired in post-cutover sweep: `PostSnapshotStoragePort`, `SeenRecordStoragePort`,
`PromiseStoragePort` — the data they represented (Social baselines, dedup seen
records, Civic promises) is now persisted directly by the corresponding Edge
Functions.

## Authentication

- **User endpoints:** Session cookie (SaaS) or Bearer JWT (Supabase) —
  `get_current_user()` in `dependencies/auth.py` delegates to
  `providers.get_auth()` which currently returns `SupabaseAuth`.
- **Public API (`/api/v1/*`):** Bearer `cj_…` API key validated by
  `api_key_service.py`.
- **MuckRock proxy:** none at the FastAPI layer — `muckrock_proxy.py`
  forwards to Supabase EFs which handle the OAuth + webhook HMAC.

## Local development

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload

# tests
python3 -m pytest tests/unit/ -v
```

## Pre-commit

Backend tests must pass before every commit that touches `backend/`:

```bash
cd backend && source .venv/bin/activate && python3 -m pytest tests/unit/ -v
```

See `backend/tests/CLAUDE.md` for layout and mocking conventions.

## See also

- `docs/architecture/api-surface-audit.md` — authoritative post-cutover HTTP surface
- `docs/supabase/architecture-overview.md` — who-calls-what diagram for the EF side
- `docs/supabase/edge-functions.md` — every Edge Function
- `docs/oss/adapter-pattern.md` — port/adapter design (with post-cutover banner)
- `cli/CLAUDE.md` — `cojo` CLI release + auth precedence
