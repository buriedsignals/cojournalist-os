# coJournalist Deployment Agent Instructions

## Recommended: Use the Setup Skill

The easiest way to deploy is to load the setup skill file into your AI coding agent:

```
Read automation/SETUP_AGENT.md and set up coJournalist
```

The skill walks you through the entire process interactively with pre-flight checks, API key collection, and deployment verification.

**The instructions below are the manual equivalent if you prefer to follow step-by-step.**

---

You are deploying coJournalist, an AI-powered local news monitoring platform, for a newsroom. Follow these instructions step-by-step. Ask the user for input when needed.

## Prerequisites

Before starting, confirm the user has:
1. A GitHub account with the `gh` CLI installed and authenticated
2. API keys for: Gemini, Firecrawl, Resend, Apify (required), MapTiler and OpenRouter (optional)
3. A Supabase account (https://supabase.com) OR Docker installed for self-hosting
4. A Render account (https://render.com) OR Docker for self-hosting

If any prerequisite is missing, help them set it up before proceeding.

No license key is required — the repository is public and self-hosting is free under the Sustainable Use License.

## Step 1: Fork the Repository

```bash
gh repo fork buriedsignals/cojournalist-os --clone
cd cojournalist-os
git remote add upstream https://github.com/buriedsignals/cojournalist-os.git
```

## Step 2: Set Up Supabase

Ask the user: "Do you want to use Supabase Cloud (managed) or self-hosted Docker?"

### Option A: Supabase Cloud (Managed)

1. Ask the user to create a Supabase project at https://supabase.com if they haven't already
2. Collect from the user (Settings -> API in Supabase dashboard):
   - Project URL (e.g., `https://xxx.supabase.co`)
   - Anon key
   - Service role key
   - JWT secret
   - Project ref (from the URL)
3. Enable extensions:

```bash
npx supabase link --project-ref <project_ref>
npx supabase db execute --sql "CREATE EXTENSION IF NOT EXISTS \"vector\";"
npx supabase db execute --sql "CREATE EXTENSION IF NOT EXISTS \"pg_cron\";"
npx supabase db execute --sql "CREATE EXTENSION IF NOT EXISTS \"pg_net\";"
```

4. Run migrations:

```bash
npx supabase db push
```

5. Deploy Edge Functions:

```bash
npx supabase functions deploy execute-scout
npx supabase functions deploy manage-schedule
```

6. Set Edge Function secrets:

```bash
INTERNAL_SERVICE_KEY=$(openssl rand -hex 32)
npx supabase secrets set "INTERNAL_SERVICE_KEY=${INTERNAL_SERVICE_KEY}"
```

### Option B: Self-Hosted Docker

1. Generate secrets:

```bash
POSTGRES_PASSWORD=$(openssl rand -hex 32)
SUPABASE_JWT_SECRET=$(openssl rand -hex 32)
INTERNAL_SERVICE_KEY=$(openssl rand -hex 32)
```

2. Generate Supabase JWT keys (anon and service_role) signed with the JWT secret. Use https://supabase.com/docs/guides/self-hosting/docker#generate-api-keys for instructions.

3. Write the `.env` file in `deploy/docker/` with all the collected values.

4. Start the stack:

```bash
cd deploy/docker
cp .env.example .env
# Edit .env with the values above
docker compose up -d
```

5. Run migrations:

```bash
docker compose exec db psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/001_initial.sql
# Repeat for each migration file in order
```

## Step 3: Collect API Keys

Ask the user for each API key. Present them one at a time with the signup URL:

| Key | Service | Signup URL |
|-----|---------|------------|
| `GEMINI_API_KEY` | Google Gemini (LLM + embeddings) | https://aistudio.google.com |
| `FIRECRAWL_API_KEY` | Firecrawl (web scraping) | https://www.firecrawl.dev |
| `RESEND_API_KEY` | Resend (email) | https://resend.com |
| `APIFY_API_TOKEN` | Apify (social scraping) | https://www.apify.com |
| `PUBLIC_MAPTILER_API_KEY` | MapTiler (geocoding, optional) | https://www.maptiler.com |
| `OPENROUTER_API_KEY` | OpenRouter (alt LLMs, optional) | https://openrouter.ai |

## Step 4: Write Configuration

Create the `.env` file in the repository root:

```bash
cat > .env << 'EOF'
DEPLOYMENT_TARGET=supabase
SUPABASE_URL=<collected>
SUPABASE_SERVICE_KEY=<collected>
SUPABASE_ANON_KEY=<collected>
SUPABASE_JWT_SECRET=<collected>
GEMINI_API_KEY=<collected>
LLM_MODEL=gemini-2.5-flash-lite
FIRECRAWL_API_KEY=<collected>
RESEND_API_KEY=<collected>
RESEND_FROM_EMAIL=scouts@newsroom.org
APIFY_API_TOKEN=<collected>
INTERNAL_SERVICE_KEY=<generated>
PUBLIC_DEPLOYMENT_TARGET=supabase
PUBLIC_SUPABASE_URL=<same as SUPABASE_URL>
PUBLIC_SUPABASE_ANON_KEY=<same as SUPABASE_ANON_KEY>
EOF
```

Replace all `<collected>` and `<generated>` placeholders with actual values.

## Step 5: Deploy

Ask the user: "Deploy to Render or Docker Compose?"

### Option A: Render

1. Tell the user to go to https://dashboard.render.com -> New -> Blueprint
2. Connect their forked repo
3. Render reads `deploy/render/render.yaml`
4. Fill in env vars from the `.env` file
5. Wait for deployment to complete
6. Note the backend URL (e.g., `https://cojournalist-api.onrender.com`)

### Option B: Docker Compose

```bash
cp .env deploy/docker/.env
cd deploy/docker
docker compose up -d
```

Wait 30 seconds for services to start, then verify:

```bash
docker compose ps
```

## Step 6: Install Sync Action

```bash
# Copy the sync workflow to the fork
mkdir -p .github/workflows
cp automation/sync-upstream.yml .github/workflows/sync-upstream.yml

# Optional: set the Render deploy hook so merges auto-deploy
# gh secret set RENDER_DEPLOY_HOOK  (ask user for the URL from Render dashboard)

# Commit and push
git add .github/workflows/sync-upstream.yml
git commit -m "ci: install sync-upstream action"
git push origin main
```

## Step 7: Verify

Run a health check:

```bash
# For Render:
curl https://<render-url>/api/health

# For Docker:
curl http://localhost:8080/api/health
```

Expected: `{"status": "healthy"}`

Then open the frontend URL in a browser:
- Render: The frontend static site URL from Render dashboard
- Docker: http://localhost:3000

Tell the user to:
1. Create an account (email + password via Supabase Auth)
2. Complete onboarding (timezone, language, location)
3. Create their first scout to verify everything works

## Troubleshooting

If the health check fails:
- **Render:** Check Render dashboard logs
- **Docker:** Run `docker compose logs backend` and `docker compose logs db`
- Common issues: missing env vars, database not ready, wrong Supabase URL

If Edge Functions fail:
- Check `supabase functions serve` locally for errors
- Verify `INTERNAL_SERVICE_KEY` matches between Edge Functions and backend

If migrations fail:
- Check that `pg_cron` and `vector` extensions are enabled
- For managed Supabase, these may need to be enabled in the dashboard first
