# coJournalist Self-Hosted Setup

Deploy coJournalist on your own infrastructure with automated setup.

## Triggers

- "set up coJournalist"
- "deploy coJournalist"
- "install coJournalist"
- "configure coJournalist"

## Prerequisites

Before starting, you need:
- A coJournalist license key (starts with `cjl_`)
- A Supabase account (managed cloud at supabase.com, or self-hosted via Docker)
- API keys for: Gemini, Firecrawl, Resend, and Apify
- Optional: MapTiler API key (for geocoding), OpenRouter API key (for non-Gemini models)

## Process

### Step 1: Pre-flight Checks

Verify the environment is ready:

```bash
# Required tools
command -v git || echo "MISSING: git"
command -v node || echo "MISSING: node"
command -v npm || echo "MISSING: npm"
command -v supabase || echo "MISSING: Supabase CLI (npm install -g supabase)"

# Node version (must be 22 LTS)
node --version
```

If any tools are missing, help the user install them before proceeding.

### Step 2: Validate License Key

Ask the user for their license key, then validate it:

```bash
export COJOURNALIST_LICENSE_KEY="<user's key>"

RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "https://www.cojournalist.ai/api/license/validate" \
    -H "Content-Type: application/json" \
    -d "{\"key\": \"${COJOURNALIST_LICENSE_KEY}\"}" \
    --max-time 10 2>/dev/null || echo -e "\n000")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP: $HTTP_CODE"
echo "$BODY"
```

- If 200: license is valid, continue
- If 403: license is invalid or expired, stop and inform the user
- If 000 (network error): warn but continue (fail-open policy)

### Step 3: Clone the Repository

```bash
git clone https://github.com/buriedsignals/cojournalist-os.git
cd cojournalist-os
```

### Step 4: Collect API Keys

Ask the user for each key interactively. Explain what each service is used for:

| Key | Service | Purpose | Required |
|-----|---------|---------|----------|
| `GEMINI_API_KEY` | Google AI Studio | LLM (default model) + embeddings | Yes |
| `FIRECRAWL_API_KEY` | Firecrawl | Web scraping and search | Yes |
| `RESEND_API_KEY` | Resend | Email notifications | Yes |
| `APIFY_API_TOKEN` | Apify | Social media scraping | Yes |
| `PUBLIC_MAPTILER_API_KEY` | MapTiler | Geocoding for location search | No |
| `OPENROUTER_API_KEY` | OpenRouter | Alternative LLM provider | No |

If the user doesn't have an API key, provide the signup URL:
- Gemini: https://aistudio.google.com/apikey
- Firecrawl: https://firecrawl.dev
- Resend: https://resend.com
- Apify: https://apify.com
- MapTiler: https://www.maptiler.com
- OpenRouter: https://openrouter.ai

### Step 5: Set Up Supabase

Ask the user: **"Are you using managed Supabase (cloud) or self-hosted (Docker)?"**

#### Managed Supabase (recommended)

1. Ask for their Supabase project URL and keys:
   - `SUPABASE_URL` (e.g., `https://xxxxx.supabase.co`)
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_KEY`
   - `SUPABASE_JWT_SECRET` (from Project Settings > API)
   - `DATABASE_URL` (from Project Settings > Database > Connection string, use the "URI" format)

2. Link the project:
   ```bash
   supabase link --project-ref <project-ref>
   ```

3. Run migrations:
   ```bash
   supabase db push
   ```

4. Deploy Edge Functions:
   ```bash
   supabase functions deploy execute-scout
   supabase functions deploy manage-schedule
   ```

#### Self-hosted (Docker)

1. Navigate to the Docker deployment:
   ```bash
   cd deploy/docker
   ```

2. Copy and edit the environment file:
   ```bash
   cp .env.example .env
   # Edit .env with the collected API keys
   ```

3. Start the stack:
   ```bash
   docker compose up -d
   ```

4. Wait for services to be healthy, then run migrations:
   ```bash
   supabase db push --db-url "postgresql://postgres:${POSTGRES_PASSWORD}@localhost:5432/postgres"
   ```

### Step 6: Write Environment File

Generate the `.env` file with all collected values:

```bash
cat > .env << EOF
DEPLOYMENT_TARGET=supabase
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
DATABASE_URL=${DATABASE_URL}
GEMINI_API_KEY=${GEMINI_API_KEY}
LLM_MODEL=gemini-2.5-flash-lite
FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
RESEND_API_KEY=${RESEND_API_KEY}
APIFY_API_TOKEN=${APIFY_API_TOKEN}
INTERNAL_SERVICE_KEY=$(openssl rand -hex 32)
PUBLIC_MAPTILER_API_KEY=${PUBLIC_MAPTILER_API_KEY:-}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
EOF
```

### Step 7: Deploy the Application

Ask the user: **"Deploy on Render (PaaS) or Docker (self-hosted)?"**

#### Render

1. Create a new Web Service on render.com
2. Connect to the cloned GitHub repo
3. Use `deploy/render/render.yaml` as the blueprint
4. Set the environment variables from `.env`

#### Docker

If not already running from Step 5:
```bash
cd deploy/docker
docker compose up -d
```

### Step 8: Install Auto-Sync (Optional)

Set up weekly auto-updates from upstream:

1. Copy the sync action to the repo:
   ```bash
   mkdir -p .github/workflows
   cp automation/sync-upstream.yml .github/workflows/
   ```

2. Add the license key as a GitHub secret:
   ```bash
   gh secret set COJOURNALIST_LICENSE_KEY --body "${COJOURNALIST_LICENSE_KEY}"
   ```

3. Optionally add deploy hook for auto-redeploy:
   ```bash
   gh secret set RENDER_DEPLOY_HOOK --body "<your-render-deploy-hook-url>"
   ```

### Step 9: Verify Deployment

```bash
# Check the backend health endpoint
BACKEND_URL="${SUPABASE_URL:-http://localhost:8000}"
curl -s "${BACKEND_URL}/api/health" | head -20

# If healthy, the response should include {"status": "ok"}
```

If the health check fails, check:
- Are all services running? (`docker compose ps` or Render dashboard)
- Are environment variables set correctly?
- Can the backend reach the Supabase database?
- Are Edge Functions deployed? (`supabase functions list`)

### Step 10: Create First User

Navigate to the frontend URL in a browser:
- Render: the static site URL from the dashboard
- Docker: `http://localhost:3000`

Sign up with email/password (Supabase Auth). This creates your first user.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `connection refused` on database | Check DATABASE_URL, ensure Supabase is running |
| Edge Functions not triggering | Verify `supabase functions deploy` succeeded, check function logs |
| Emails not sending | Verify RESEND_API_KEY, check Resend dashboard for delivery status |
| `statement_cache_size` error | Ensure DATABASE_URL points to the direct connection (port 5432), not the pooler (port 6543) |
| pgvector dimension mismatch | Default is 1536 (Gemini). If using a different model, update migration |
