# coJournalist Deployment Guide

Two deployment paths: **Managed** (Supabase Cloud + Render) and **Self-Hosted** (Docker Compose). Both run the same code.

**Estimated time:** 1-2 hours with API keys ready. With a license key, `automation/setup.sh` automates most steps.

---

## Prerequisites

Before starting either path, you need API keys for external services:

| Service | Purpose | Get it at |
|---------|---------|-----------|
| **Gemini** | LLM + embeddings (required) | [aistudio.google.com](https://aistudio.google.com) |
| **Firecrawl** | Web scraping (required) | [firecrawl.dev](https://www.firecrawl.dev) |
| **Resend** | Email notifications (required) | [resend.com](https://resend.com) |
| **Apify** | Social media scraping (required for Social Scout) | [apify.com](https://www.apify.com) |
| **MapTiler** | Geocoding (optional, for location features) | [maptiler.com](https://www.maptiler.com) |
| **OpenRouter** | Alternative LLMs (optional) | [openrouter.ai](https://openrouter.ai) |

---

## Path 1: Managed (Supabase Cloud + Render)

Best for: Newsrooms that want minimal infrastructure management.

### 1.1 Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note your project URL, anon key, service role key, and JWT secret (Settings -> API)
3. Enable the required extensions in SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_cron";
CREATE EXTENSION IF NOT EXISTS "pg_net";
```

### 1.2 Run Migrations

In the Supabase SQL Editor, run each migration file from `supabase/migrations/` in order. The files are numbered sequentially (e.g., `001_initial.sql`, `002_indexes.sql`).

Alternatively, use the Supabase CLI:

```bash
supabase db push --project-ref YOUR_PROJECT_REF
```

### 1.3 Deploy Edge Functions

```bash
supabase functions deploy execute-scout --project-ref YOUR_PROJECT_REF
supabase functions deploy manage-schedule --project-ref YOUR_PROJECT_REF
```

Set the Edge Function secrets:

```bash
supabase secrets set INTERNAL_SERVICE_KEY=your-service-key --project-ref YOUR_PROJECT_REF
```

### 1.4 Deploy to Render

1. Fork the `buriedsignals/cojournalist-os` repo to your GitHub account
2. Go to [render.com](https://render.com) -> "New Blueprint Instance"
3. Connect your forked repo
4. Render reads `deploy/render/render.yaml` and creates both services
5. Fill in the environment variables when prompted:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_SERVICE_KEY`: Service role key
   - `SUPABASE_ANON_KEY`: Anon key
   - `SUPABASE_JWT_SECRET`: JWT secret
   - `GEMINI_API_KEY`, `FIRECRAWL_API_KEY`, `RESEND_API_KEY`, `APIFY_API_TOKEN`
   - `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY` (for frontend)
   - `PUBLIC_MAPTILER_API_KEY` (optional)

### 1.5 Verify

```bash
curl https://your-render-url.onrender.com/api/health
```

Expected: `{"status": "healthy"}`

---

## Path 2: Self-Hosted (Docker Compose)

Best for: Newsrooms with Docker infrastructure or wanting full control.

### 2.1 Clone and Configure

```bash
git clone https://github.com/buriedsignals/cojournalist-os.git
cd cojournalist-os/deploy/docker
cp .env.example .env
```

Edit `.env` with your API keys and generated secrets:

```bash
# Generate secrets
openssl rand -hex 32  # Use for SUPABASE_JWT_SECRET
openssl rand -hex 32  # Use for INTERNAL_SERVICE_KEY
openssl rand -hex 32  # Use for POSTGRES_PASSWORD
```

### 2.2 Generate Supabase Keys

The anon and service role keys are JWTs signed with your `SUPABASE_JWT_SECRET`. Generate them:

```bash
# Install supabase CLI if needed: npm install -g supabase
# Or generate JWTs manually — see https://supabase.com/docs/guides/self-hosting

# Anon key payload: {"role": "anon", "iss": "supabase", "iat": ..., "exp": ...}
# Service key payload: {"role": "service_role", "iss": "supabase", "iat": ..., "exp": ...}
```

Add the generated keys to `.env` as `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_KEY`.

### 2.3 Start the Stack

```bash
docker compose up -d
```

Wait for all services to be healthy:

```bash
docker compose ps
```

All services should show `Up` status.

### 2.4 Run Migrations

```bash
docker compose exec db psql -U postgres -d postgres \
  -f /docker-entrypoint-initdb.d/001_initial.sql
```

Repeat for each migration file in sequence.

### 2.5 Verify

```bash
curl http://localhost:8080/api/health
```

Expected: `{"status": "healthy"}`

Open http://localhost:3000 in your browser to access the frontend.

---

## Automated Setup (License Key Required)

If you have a coJournalist license key, the setup can be automated:

```bash
export COJOURNALIST_LICENSE_KEY="cjl_your-key-here"
bash automation/setup.sh
```

This handles forking, API key collection, migration, deployment, and verification. See `automation/AGENT_INSTRUCTIONS.md` for AI-assisted setup.

---

## Updating

### With License Key (Automatic)

The `sync-upstream.yml` GitHub Action runs weekly and:
1. Validates your license key
2. Fetches updates from the upstream OSS repo
3. Runs any new database migrations
4. Triggers a Render deploy (or rebuilds Docker containers)

### Without License Key (Manual)

```bash
git remote add upstream https://github.com/buriedsignals/cojournalist-os.git
git fetch upstream
git merge upstream/main
# Check for new files in supabase/migrations/ and run them
# Restart services
```
