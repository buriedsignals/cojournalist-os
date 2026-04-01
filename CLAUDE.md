# coJournalist

<!-- test: verify Claude GitHub Actions workflows -->

## Deployment Workflow - MANDATORY

**NEVER push directly to `main`.** All changes go through a branch + PR. This is not optional.

1. **Check for worktrees first:**
   ```bash
   git worktree list
   ```
   If a worktree exists for the current task, work there.

2. **Create a branch** from `main` (or use `develop`):
   ```bash
   git checkout -b my-feature main
   ```

3. **Push the branch and open a PR to `main`:**
   ```bash
   git push -u origin my-feature
   gh pr create --title "..." --body "..."
   ```

4. **Wait for CI to pass** — 4 required checks must be green:
   - `build-frontend` — SvelteKit build
   - `test-frontend` — Vitest suite
   - `test-backend` — pytest unit tests
   - `lint` — svelte-check

5. **Merge the PR** — Render auto-deploys backend from `main`.

**Why:** Pushing to `main` triggers a Render deploy immediately with no safety net. The PR flow ensures CI passes and Claude reviews the code before anything reaches production.

---

## Node Version - IMPORTANT

**This project requires Node 22 LTS.** The Dockerfile and `frontend/.nvmrc` are pinned to Node 22. Using a different major version (especially Node 25+ with npm 11) will generate an incompatible `package-lock.json` that breaks the Render build (`npm ci` fails). Always run `nvm use` in `frontend/` before `npm install`.

---

AI-powered local news monitoring platform. Users create "scouts" that monitor websites, local news, or search queries on schedules, receiving email notifications when criteria are met. Scouts can be scoped by **location** (geo-targeted) or **topic** (keyword-based), or both.

**Production URL:** `https://www.cojournalist.ai` — API at `/api/*`

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | SvelteKit (static SPA), TailwindCSS |
| Backend | FastAPI (Python), hosted on Render — production at `https://www.cojournalist.ai/api` |
| Database | DynamoDB (scout metadata + run history) |
| Scheduling | AWS EventBridge Scheduler |
| Auth | MuckRock OAuth 2.0 (SaaS, session cookies) / Supabase Auth (OSS, Bearer JWT) |
| AI | Gemini 2.5 Flash-Lite (default LLM, direct API), OpenRouter (fallback), Firecrawl (web search) |
| Email | Resend |
| Maps | MapTiler (geocoding) |

## Project Structure

```
/
├── frontend/          # SvelteKit SPA
├── backend/           # FastAPI Python backend
├── aws/               # Lambda functions + infrastructure
└── docs/              # Detailed architecture docs
```

## Key Documentation

- **AWS Architecture**: `docs/architecture/aws-architecture.md` - Lambda functions, DynamoDB schema, EventBridge
- **API Endpoints**: `docs/architecture/fastapi-endpoints.md` - All REST endpoints with examples
- **Page Scouts**: `docs/features/web-scouts.md` - Website change detection
- **Records & Dedup**: `docs/architecture/records-and-deduplication.md` - DynamoDB records, dedup layers
- **Entitlements & Credits**: `docs/muckrock/plans-and-entitlements.md` - MuckRock entitlement tiers, credit costs
- **MuckRock Integration**: `docs/muckrock/oauth-integration.md` - OAuth flow, session management
- **Team Plan**: `docs/muckrock/entitlements-team-design.md` - Shared credit pool, ORG# records, seat management
- **OSS / Self-Hosted**: `docs/oss/` - Architecture, adapters, Supabase, licensing, deployment, automation
- **AWS Deployment**: `aws/README.md` - Lambda deployment commands

## Service Documentation

Detailed docs for each sidebar service in `docs/features/`:

| Service | File | Description |
|---------|------|-------------|
| Page Scout (type `web`) | `web-scouts.md` | Firecrawl changeTracking, per-scout baselines, criteria analysis |
| Location Scout (type `pulse`) | `pulse.md` | Location-based monitoring — niche local sources by default |
| Beat Scout (type `pulse`) | `pulse.md` | Topic/criteria monitoring — reliable sources by default |
| Scrape | `scrape.md` | Firecrawl extraction, format options |
| Social Scout (type `social`) | `social.md` | Social media monitoring, post diffing, Apify scraping |
| Civic Scout (type `civic`) | `civic.md` | Council website monitoring, PDF parsing, promise extraction |
| Feed & Export | `feed.md` | Information units, export generation |

## Sidebar Services

| View | Internal Type | Router | Orchestrator |
|------|---------------|--------|--------------|
| Page Scout | `web` | `scouts.py` | `scout_service.py` |
| Location Scout | `pulse` | `pulse.py` | `pulse_orchestrator.py` |
| Beat Scout | `pulse` | `pulse.py` | `pulse_orchestrator.py` |
| Social Scout | `social` | `social.py` | `social_orchestrator.py` |
| Civic Scout | `civic` | `civic.py` | `civic_orchestrator.py` |
| Scrape | N/A | `data_extractor.py` | `firecrawl_client.py` |
| Feed / Export | N/A | `export.py` | `export_generator.py` |

## Admin Dashboard (SaaS-only, stripped from OSS mirror)

Revenue reporting for MuckRock pilot invoicing. Accessible at `/api/admin/` (browser) by users in `ADMIN_EMAILS`.

| File | Purpose |
|------|---------|
| `backend/app/routers/admin.py` | Dashboard HTML + JSON API endpoints |
| `backend/app/services/admin_report_service.py` | Report generation, metrics, email template |
| `backend/app/adapters/aws/admin_storage.py` | USAGE# record storage + aggregate queries |
| `backend/app/schemas/admin.py` | Pydantic response models |
| `backend/app/dependencies/auth.py` | `require_admin` dependency (ADMIN_EMAILS check) |

**USAGE# records:** Written on every credit decrement (fire-and-forget from `decrement_credit()` in `billing.py`). Stored in DynamoDB with 365-day TTL. PK is `ORG#{id}` or `USER#{id}`, SK is `USAGE#{timestamp}#{uuid}`.

**Endpoints:**
- `GET /api/admin/` — Browser dashboard (metrics + current month invoice)
- `GET /api/admin/usage?start_date=X&end_date=Y` — Query usage records
- `GET /api/admin/metrics` — Users by tier, orgs, scouts
- `POST /api/admin/report/monthly?year=X&month=Y` — Invoice JSON
- `POST /api/admin/report/send-email?year=X&month=Y` — Send report via Resend

## Directory-Specific Guides

- `/aws/CLAUDE.md` - AWS infrastructure and Lambda details
- `/backend/CLAUDE.md` - FastAPI structure and services
- `/frontend/CLAUDE.md` - SvelteKit components and stores
- `/docs/CLAUDE.md` - Documentation structure and guidelines

## Scout Types

| Type | UI Name | Purpose | Scope | Notification |
|------|---------|---------|-------|--------------|
| `web` | Page Scout | Monitor URL for content changes | URL (+ optional topic) | When criteria match |
| `pulse` | Location Scout | Location-based news monitoring | Location (+ optional criteria) | Always |
| `pulse` | Beat Scout | Topic/criteria news monitoring | Criteria (no location) | Always |
| `social` | Social Scout | Monitor social media profiles | Platform + handle | Always |
| `civic` | Civic Scout | Monitor council meetings for promises | Domain + confirmed URLs | When promises found |

**Location Scout vs Beat Scout:** Both use the same backend `pulse` pipeline. Location Scout defaults to **niche** sources (local blogs, community sites); Beat Scout defaults to **reliable** sources (established outlets). Source mode is togglable in both. Location Scout requires a location and optionally accepts criteria; Beat Scout requires criteria only.

**Page Scout change detection:** Uses Firecrawl `changeTracking` with per-scout `tag` parameter. Each scout has its own baseline. See `docs/features/web-scouts.md`.

**Page Scout first-run extraction:** Users control whether to import existing page data via "Import current page data" toggle. OFF (default) establishes baseline only; ON extracts content to knowledge base.

## Data Flow

```
User creates scout → FastAPI → AWS API Gateway → Lambda creates:
                                                  ├── EventBridge Schedule (cron)
                                                  └── DynamoDB SCRAPER# record

On schedule → EventBridge → scraper-lambda → FastAPI scouts endpoint:
                                             ├── Execute scout logic
                                             ├── AI analysis
                                             ├── Send notification (Resend)
                                             └── Decrement credits (MuckRock entitlements)
                            ↓
              scraper-lambda stores TIME# record in DynamoDB
```

## Pre-Commit Verification - MANDATORY

**Run these checks before every commit that touches frontend code:**

```bash
cd frontend

# 1. If you added/changed any m.*() calls in .svelte or .ts files:
#    Ensure ALL keys exist in messages/en.json AND all 12 language files.
#    Then recompile:
npm run paraglide:compile

# 2. Lint (catches missing i18n keys, type errors, Svelte issues):
npm run check

# 3. Tests:
npm test
```

**Common failure: "Property 'xxx' does not exist on type 'typeof messages'"**
This means a `m.some_key()` call exists in a component but the key is missing from `messages/en.json`. Fix: add the key to `en.json` and all other language files (`da`, `de`, `es`, `fi`, `fr`, `it`, `nl`, `no`, `pl`, `pt`, `sv`), then recompile.

**Backend tests:**
```bash
cd backend && python3 -m pytest tests/unit/ -v
```

See `backend/tests/CLAUDE.md` and `frontend/src/tests/CLAUDE.md` for details.

## CI/CD Pipeline

CI runs automatically on push to `develop` and on PRs to `main`. See **Deployment Workflow** above for the mandatory process.

### GitHub Actions Workflows

| File | Purpose | Trigger |
|------|---------|---------|
| `ci.yml` | Build, test, lint (4 required checks) | Push to `develop`, PR to `main` |
| `claude.yml` | Claude PR assistant (`@claude` in issues/PRs) | Issue/PR comments |
| `claude-code-review.yml` | Auto-review on PRs | PR opened/synchronized |

### Deploy pipeline

```
feature branch → push → CI runs
                          ↓
               PR to main → CI + Claude review
                          ↓
               merge → Render auto-deploys backend
```

## Environment Variables

### Backend (Render)
- `MUCKROCK_CLIENT_ID` - MuckRock OAuth client ID
- `MUCKROCK_CLIENT_SECRET` - MuckRock OAuth client secret
- `SESSION_SECRET` - JWT session signing key
- `OAUTH_REDIRECT_BASE` - Public URL the browser sees (needed behind proxy, e.g. `http://localhost:5173`)
- `OPENROUTER_API_KEY` - AI access
- `LLM_MODEL` - LLM model identifier (default: `gemini-2.5-flash-lite`). Gemini models route to Google AI direct API; others route to OpenRouter.
- `GEMINI_API_KEY` - Gemini API key (LLM + multimodal embeddings)
- `FIRECRAWL_API_KEY` - Web scraping
- `APIFY_API_TOKEN` - Apify API token (social media scraping)
- `RESEND_API_KEY` - Email notifications
- `INTERNAL_SERVICE_KEY` - Lambda → FastAPI auth
- `AWS_API_BASE_URL` - AWS API Gateway URL

### Frontend (Build-time)
- `PUBLIC_MAPTILER_API_KEY` - Geocoding

### AWS Lambda
- See `aws/README.md` for Lambda-specific env vars
