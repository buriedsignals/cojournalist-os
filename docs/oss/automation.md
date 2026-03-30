# Phase 5: Automation Scripts Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the paid DevOps automation that license key holders use for one-click deployment and automatic updates. Three files: `setup.sh` (bootstrap), `sync-upstream.yml` (GitHub Action for auto-updates), and `AGENT_INSTRUCTIONS.md` (AI agent prompt).

**Architecture:** All three files live in `automation/` in the public OSS repo. `setup.sh` and `sync-upstream.yml` validate the license key via `POST /api/license/validate` before executing. The validation follows a "fail open on network errors, fail closed on explicit rejections" policy -- paying customers are never blocked by transient server issues.

**Tech Stack:** Bash, GitHub Actions YAML, Supabase CLI, Render API

**Depends on:** Phase 3 (OSS repo exists, deploy configs ready) + Phase 4 (license validation endpoint works).

---

## File Structure

```
automation/
├── setup.sh                    # One-time bootstrap script (license-gated)
├── sync-upstream.yml            # GitHub Action for weekly auto-updates (license-gated)
└── AGENT_INSTRUCTIONS.md        # Prompt for Claude Code / Codex AI agents
```

---

## Task 5.1: setup.sh

**Files:**
- Create: `automation/setup.sh`

Complete working bash script for one-click deployment. Validates license, forks repo, collects API keys, initializes Supabase, runs migrations, deploys edge functions, writes `.env`, deploys to Render or Docker, installs sync action, and runs health check.

- [ ] **Step 1: Create `automation/setup.sh`**

```bash
#!/usr/bin/env bash
# =============================================================================
# coJournalist Setup Script
# =============================================================================
#
# Automated bootstrap for deploying coJournalist on Supabase + Render or Docker.
# Requires a valid license key (COJOURNALIST_LICENSE_KEY environment variable).
#
# Usage:
#   export COJOURNALIST_LICENSE_KEY="cjl_your-key-here"
#   bash setup.sh
#
# What this script does:
#   1. Validates your license key
#   2. Forks the OSS repo to your GitHub account
#   3. Collects API keys interactively
#   4. Initializes Supabase project (or connects to existing)
#   5. Runs database migrations
#   6. Deploys Edge Functions
#   7. Writes .env configuration
#   8. Deploys to Render or starts Docker Compose
#   9. Installs sync-upstream.yml GitHub Action
#  10. Runs health check
#
# =============================================================================
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# API endpoint for license validation
LICENSE_API="https://www.cojournalist.ai/api/license/validate"

# Upstream OSS repo
UPSTREAM_REPO="buriedsignals/cojournalist-os"

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

prompt_required() {
    local var_name="$1"
    local prompt_text="$2"
    local value=""

    while [ -z "$value" ]; do
        read -rp "  $prompt_text: " value
        if [ -z "$value" ]; then
            echo "    This field is required."
        fi
    done
    eval "$var_name='$value'"
}

prompt_optional() {
    local var_name="$1"
    local prompt_text="$2"
    local default_value="${3:-}"
    local value=""

    if [ -n "$default_value" ]; then
        read -rp "  $prompt_text [$default_value]: " value
        value="${value:-$default_value}"
    else
        read -rp "  $prompt_text (optional, press Enter to skip): " value
    fi
    eval "$var_name='$value'"
}

check_command() {
    if ! command -v "$1" &>/dev/null; then
        log_error "$1 is required but not installed."
        echo "  Install it: $2"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Step 1: Validate license key
# ---------------------------------------------------------------------------

validate_license() {
    log_info "Validating license key..."

    LICENSE_KEY="${COJOURNALIST_LICENSE_KEY:-}"

    if [ -z "$LICENSE_KEY" ]; then
        log_error "COJOURNALIST_LICENSE_KEY environment variable not set."
        echo "  Get your license key at https://www.cojournalist.ai/license"
        echo "  Then run: export COJOURNALIST_LICENSE_KEY=\"cjl_your-key-here\""
        exit 1
    fi

    # Validate against the API
    RESPONSE=$(curl -s -X POST -w "\n%{http_code}" \
        -H "Content-Type: application/json" \
        -d "{\"key\": \"${LICENSE_KEY}\"}" \
        "${LICENSE_API}" \
        --max-time 10 2>/dev/null || echo -e "\n000")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" = "200" ]; then
        EXPIRES=$(echo "$BODY" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4)
        STATUS=$(echo "$BODY" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        EMAIL=$(echo "$BODY" | grep -o '"customer_email":"[^"]*"' | cut -d'"' -f4)
        log_success "License valid (email: ${EMAIL}, expires: ${EXPIRES}, status: ${STATUS})"

        if [ "$STATUS" = "cancelled" ]; then
            log_warn "Your subscription is cancelled. License works until ${EXPIRES}."
        fi
        if [ "$STATUS" = "past_due" ]; then
            log_warn "Payment past due. License works until ${EXPIRES}. Please update payment."
        fi
    elif [ "$HTTP_CODE" = "403" ]; then
        ERROR=$(echo "$BODY" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
        log_error "License validation failed: ${ERROR}"
        exit 1
    elif [ "$HTTP_CODE" = "000" ]; then
        # Network error or endpoint down -- grace period
        log_warn "Could not reach license server. Proceeding with grace period."
        echo "  If this persists, check https://www.cojournalist.ai/status"
    else
        log_warn "Unexpected response (HTTP ${HTTP_CODE}). Proceeding anyway."
    fi
}

# ---------------------------------------------------------------------------
# Step 2: Check prerequisites
# ---------------------------------------------------------------------------

check_prerequisites() {
    log_info "Checking prerequisites..."

    check_command "git" "https://git-scm.com/downloads"
    check_command "gh" "brew install gh (macOS) or https://cli.github.com"
    check_command "curl" "should be pre-installed on most systems"
    check_command "jq" "brew install jq (macOS) or apt install jq (Linux)"

    # Check gh auth status
    if ! gh auth status &>/dev/null; then
        log_error "GitHub CLI not authenticated. Run: gh auth login"
        exit 1
    fi

    log_success "All prerequisites met"
}

# ---------------------------------------------------------------------------
# Step 3: Fork the OSS repo
# ---------------------------------------------------------------------------

fork_repo() {
    log_info "Forking the coJournalist OSS repo..."

    # Check if fork already exists
    GH_USER=$(gh api user --jq '.login')

    if gh repo view "${GH_USER}/cojournalist-os" &>/dev/null; then
        log_warn "Fork already exists: ${GH_USER}/cojournalist-os"
        read -rp "  Use existing fork? (y/n): " use_existing
        if [ "$use_existing" != "y" ]; then
            log_error "Please delete the existing fork first, then re-run setup."
            exit 1
        fi
    else
        gh repo fork "${UPSTREAM_REPO}" --clone=false
        log_success "Forked to ${GH_USER}/cojournalist-os"
    fi

    # Clone the fork
    REPO_DIR="cojournalist-os"
    if [ -d "$REPO_DIR" ]; then
        log_warn "Directory ${REPO_DIR} already exists. Using it."
    else
        gh repo clone "${GH_USER}/cojournalist-os"
        log_success "Cloned to ./${REPO_DIR}"
    fi

    cd "$REPO_DIR"

    # Set upstream remote
    if ! git remote get-url upstream &>/dev/null; then
        git remote add upstream "https://github.com/${UPSTREAM_REPO}.git"
    fi

    log_success "Repository ready"
}

# ---------------------------------------------------------------------------
# Step 4: Collect API keys
# ---------------------------------------------------------------------------

collect_api_keys() {
    log_info "Collecting API keys..."
    echo ""
    echo "  You need API keys for the following services."
    echo "  Sign up at the URLs below if you don't have accounts yet."
    echo ""

    echo "  -- Required --"
    echo ""

    echo "  Gemini (LLM + embeddings): https://aistudio.google.com"
    prompt_required GEMINI_API_KEY "Gemini API key"

    echo ""
    echo "  Firecrawl (web scraping): https://www.firecrawl.dev"
    prompt_required FIRECRAWL_API_KEY "Firecrawl API key"

    echo ""
    echo "  Resend (email notifications): https://resend.com"
    prompt_required RESEND_API_KEY "Resend API key"

    echo ""
    echo "  Apify (social media scraping): https://www.apify.com"
    prompt_required APIFY_API_TOKEN "Apify API token"

    echo ""
    echo "  -- Optional --"
    echo ""

    echo "  MapTiler (geocoding/location): https://www.maptiler.com"
    prompt_optional PUBLIC_MAPTILER_API_KEY "MapTiler API key"

    echo ""
    echo "  OpenRouter (alternative LLMs): https://openrouter.ai"
    prompt_optional OPENROUTER_API_KEY "OpenRouter API key"

    echo ""
    prompt_optional RESEND_FROM_EMAIL "Notification sender email" "scouts@newsroom.org"

    prompt_optional LLM_MODEL "LLM model" "gemini-2.5-flash-lite"

    log_success "API keys collected"
}

# ---------------------------------------------------------------------------
# Step 5: Supabase setup
# ---------------------------------------------------------------------------

setup_supabase() {
    log_info "Setting up Supabase..."
    echo ""
    echo "  Choose your Supabase deployment:"
    echo "  1) Managed (Supabase Cloud) -- recommended"
    echo "  2) Self-hosted (Docker, already running)"
    echo ""
    read -rp "  Choice (1 or 2): " supabase_choice

    if [ "$supabase_choice" = "1" ]; then
        setup_supabase_managed
    elif [ "$supabase_choice" = "2" ]; then
        setup_supabase_selfhosted
    else
        log_error "Invalid choice. Please enter 1 or 2."
        exit 1
    fi
}

setup_supabase_managed() {
    log_info "Configuring managed Supabase..."

    # Check for Supabase CLI
    if command -v supabase &>/dev/null; then
        SUPABASE_CLI="supabase"
    elif command -v npx &>/dev/null; then
        SUPABASE_CLI="npx supabase"
    else
        log_error "Supabase CLI not found. Install: npm install -g supabase"
        exit 1
    fi

    echo ""
    echo "  Go to https://supabase.com and create a new project (or use existing)."
    echo "  Then find these values in Settings -> API:"
    echo ""

    prompt_required SUPABASE_URL "Supabase project URL (e.g., https://xxx.supabase.co)"
    prompt_required SUPABASE_ANON_KEY "Supabase anon key"
    prompt_required SUPABASE_SERVICE_KEY "Supabase service role key"
    prompt_required SUPABASE_JWT_SECRET "Supabase JWT secret"

    echo ""
    prompt_required SUPABASE_PROJECT_REF "Supabase project ref (from URL, e.g., abcdefghij)"

    # Link the Supabase CLI to the project
    log_info "Linking Supabase CLI to project..."
    $SUPABASE_CLI link --project-ref "$SUPABASE_PROJECT_REF"

    # Enable required extensions
    log_info "Enabling PostgreSQL extensions..."
    $SUPABASE_CLI db execute --sql "CREATE EXTENSION IF NOT EXISTS \"vector\";"
    $SUPABASE_CLI db execute --sql "CREATE EXTENSION IF NOT EXISTS \"pg_cron\";"
    $SUPABASE_CLI db execute --sql "CREATE EXTENSION IF NOT EXISTS \"pg_net\";"
    log_success "Extensions enabled"

    # Run migrations
    log_info "Running database migrations..."
    $SUPABASE_CLI db push
    log_success "Migrations applied"

    # Deploy Edge Functions
    log_info "Deploying Edge Functions..."
    $SUPABASE_CLI functions deploy execute-scout
    $SUPABASE_CLI functions deploy manage-schedule

    # Set Edge Function secrets
    $SUPABASE_CLI secrets set "INTERNAL_SERVICE_KEY=${INTERNAL_SERVICE_KEY}"
    log_success "Edge Functions deployed"

    DEPLOY_MODE="managed"
}

setup_supabase_selfhosted() {
    log_info "Configuring self-hosted Supabase..."
    echo ""
    echo "  Enter the connection details for your self-hosted Supabase instance."
    echo ""

    prompt_required SUPABASE_URL "Supabase URL (e.g., http://localhost:8000)"
    prompt_required SUPABASE_ANON_KEY "Supabase anon key"
    prompt_required SUPABASE_SERVICE_KEY "Supabase service role key"
    prompt_required SUPABASE_JWT_SECRET "Supabase JWT secret"
    prompt_required POSTGRES_PASSWORD "PostgreSQL password"

    # Run migrations directly against the database
    log_info "Running database migrations..."
    DATABASE_URL="postgres://postgres:${POSTGRES_PASSWORD}@localhost:5432/postgres"

    for migration in supabase/migrations/*.sql; do
        if [ -f "$migration" ]; then
            log_info "Applying $(basename "$migration")..."
            psql "$DATABASE_URL" -f "$migration"
        fi
    done
    log_success "Migrations applied"

    DEPLOY_MODE="selfhosted"
}

# ---------------------------------------------------------------------------
# Step 6: Generate internal service key
# ---------------------------------------------------------------------------

generate_service_key() {
    INTERNAL_SERVICE_KEY=$(openssl rand -hex 32)
    log_success "Generated internal service key"
}

# ---------------------------------------------------------------------------
# Step 7: Write .env file
# ---------------------------------------------------------------------------

write_env_file() {
    log_info "Writing .env file..."

    cat > .env << ENVEOF
# =============================================================================
# coJournalist Configuration
# Generated by setup.sh on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# =============================================================================

# Deployment target
DEPLOYMENT_TARGET=supabase

# Supabase
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}

# LLM
GEMINI_API_KEY=${GEMINI_API_KEY}
LLM_MODEL=${LLM_MODEL}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}

# Web scraping
FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}

# Email
RESEND_API_KEY=${RESEND_API_KEY}
RESEND_FROM_EMAIL=${RESEND_FROM_EMAIL}

# Social media
APIFY_API_TOKEN=${APIFY_API_TOKEN}

# Geocoding
PUBLIC_MAPTILER_API_KEY=${PUBLIC_MAPTILER_API_KEY:-}

# Internal
INTERNAL_SERVICE_KEY=${INTERNAL_SERVICE_KEY}

# Frontend build-time vars
PUBLIC_DEPLOYMENT_TARGET=supabase
PUBLIC_SUPABASE_URL=${SUPABASE_URL}
PUBLIC_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
ENVEOF

    if [ "${DEPLOY_MODE}" = "selfhosted" ]; then
        cat >> .env << ENVEOF

# Self-hosted only
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgres://postgres:${POSTGRES_PASSWORD}@db:5432/postgres
ENVEOF
    fi

    log_success ".env file written"
}

# ---------------------------------------------------------------------------
# Step 8: Deploy
# ---------------------------------------------------------------------------

deploy() {
    log_info "Deploying coJournalist..."
    echo ""
    echo "  Choose your deployment target:"
    echo "  1) Render (managed hosting) -- recommended with managed Supabase"
    echo "  2) Docker Compose (self-hosted)"
    echo ""
    read -rp "  Choice (1 or 2): " deploy_choice

    if [ "$deploy_choice" = "1" ]; then
        deploy_render
    elif [ "$deploy_choice" = "2" ]; then
        deploy_docker
    else
        log_error "Invalid choice. Please enter 1 or 2."
        exit 1
    fi
}

deploy_render() {
    log_info "Deploying to Render..."

    GH_USER=$(gh api user --jq '.login')

    echo ""
    echo "  To deploy on Render:"
    echo ""
    echo "  1. Go to https://dashboard.render.com"
    echo "  2. Click 'New' -> 'Blueprint'"
    echo "  3. Connect your forked repo: ${GH_USER}/cojournalist-os"
    echo "  4. Render reads deploy/render/render.yaml automatically"
    echo "  5. Fill in the environment variables when prompted"
    echo ""
    echo "  Your .env file contains all the values you need."
    echo "  Copy them from: $(pwd)/.env"
    echo ""

    read -rp "  Press Enter when Render deployment is complete..."

    # Get the Render URL
    prompt_required RENDER_URL "Backend URL (e.g., https://cojournalist-api.onrender.com)"
    HEALTH_URL="${RENDER_URL}/api/health"
}

deploy_docker() {
    log_info "Starting Docker Compose stack..."

    # Copy .env to the docker deploy directory
    cp .env deploy/docker/.env

    cd deploy/docker
    docker compose up -d
    cd ../..

    log_info "Waiting for services to start (30 seconds)..."
    sleep 30

    # Check if all services are running
    cd deploy/docker
    if docker compose ps | grep -q "Exit"; then
        log_error "Some services failed to start. Check: docker compose logs"
        docker compose ps
        exit 1
    fi
    cd ../..

    log_success "Docker stack running"
    HEALTH_URL="http://localhost:8080/api/health"
}

# ---------------------------------------------------------------------------
# Step 9: Install sync-upstream.yml
# ---------------------------------------------------------------------------

install_sync_action() {
    log_info "Installing sync-upstream GitHub Action..."

    GH_USER=$(gh api user --jq '.login')

    # Create .github/workflows directory in the fork
    mkdir -p .github/workflows

    # Copy the sync action
    cp automation/sync-upstream.yml .github/workflows/sync-upstream.yml

    # Set the license key as a GitHub secret
    echo "${COJOURNALIST_LICENSE_KEY}" | gh secret set COJOURNALIST_LICENSE_KEY --repo "${GH_USER}/cojournalist-os"

    # If deploying to Render, ask for deploy hook URL
    if [ "${deploy_choice:-}" = "1" ]; then
        echo ""
        echo "  To enable automatic Render deploys on sync:"
        echo "  Go to Render Dashboard -> Your Service -> Settings -> Deploy Hook"
        echo ""
        prompt_optional RENDER_DEPLOY_HOOK "Render deploy hook URL"
        if [ -n "$RENDER_DEPLOY_HOOK" ]; then
            echo "$RENDER_DEPLOY_HOOK" | gh secret set RENDER_DEPLOY_HOOK --repo "${GH_USER}/cojournalist-os"
        fi
    fi

    # Commit and push the workflow
    git add .github/workflows/sync-upstream.yml
    git commit -m "ci: install sync-upstream GitHub Action"
    git push origin main

    log_success "Sync action installed (runs weekly on Mondays at 6 AM UTC)"
}

# ---------------------------------------------------------------------------
# Step 10: Health check
# ---------------------------------------------------------------------------

health_check() {
    log_info "Running health check..."

    RETRIES=5
    for i in $(seq 1 $RETRIES); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" --max-time 10 2>/dev/null || echo "000")

        if [ "$HTTP_CODE" = "200" ]; then
            log_success "Health check passed: ${HEALTH_URL}"
            return 0
        fi

        if [ "$i" -lt "$RETRIES" ]; then
            log_warn "Health check attempt $i/$RETRIES failed (HTTP $HTTP_CODE). Retrying in 15s..."
            sleep 15
        fi
    done

    log_error "Health check failed after $RETRIES attempts."
    echo "  Check the deployment logs for errors."
    echo "  URL: ${HEALTH_URL}"
    return 1
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    echo ""
    echo "  ======================================"
    echo "  coJournalist Setup"
    echo "  ======================================"
    echo ""

    validate_license
    check_prerequisites
    fork_repo
    generate_service_key
    collect_api_keys
    setup_supabase
    write_env_file
    deploy
    install_sync_action
    health_check

    echo ""
    echo "  ======================================"
    echo "  Setup complete!"
    echo "  ======================================"
    echo ""
    echo "  Your coJournalist instance is running at: ${HEALTH_URL%/api/health}"
    echo "  Configuration saved to: $(pwd)/.env"
    echo ""
    echo "  Next steps:"
    echo "  - Open your instance in a browser and create an account"
    echo "  - Create your first scout to start monitoring"
    echo "  - The sync action will keep your fork up to date weekly"
    echo ""
}

main "$@"
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x automation/setup.sh
```

- [ ] **Step 3: Validate bash syntax**

```bash
bash -n automation/setup.sh && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add automation/setup.sh
git commit -m "feat: add setup.sh bootstrap script for automated deployment"
```

---

## Task 5.2: sync-upstream.yml

**Files:**
- Create: `automation/sync-upstream.yml`

GitHub Action that runs weekly (Mondays 6 AM UTC) and on manual trigger. Validates license, fetches upstream changes, detects new migrations, runs them, and triggers a Render deploy.

- [ ] **Step 1: Create `automation/sync-upstream.yml`**

```yaml
# =============================================================================
# coJournalist Upstream Sync
# =============================================================================
#
# Keeps your fork up to date with the upstream coJournalist OSS repo.
# Validates license key before syncing. If license is expired or revoked,
# sync stops and your code stays at the last synced version.
#
# Required secrets:
#   COJOURNALIST_LICENSE_KEY - Your license key (set by setup.sh)
#
# Optional secrets:
#   RENDER_DEPLOY_HOOK - Render deploy hook URL for auto-deploy
#   SUPABASE_PROJECT_REF - For running new migrations automatically
#   SUPABASE_ACCESS_TOKEN - Supabase CLI access token (for migrations)
#
# =============================================================================

name: Sync Upstream

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday at 6 AM UTC
  workflow_dispatch:       # Manual trigger

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      # -------------------------------------------------------------------
      # Step 1: Validate license key
      # -------------------------------------------------------------------
      - name: Validate License
        id: license
        env:
          COJOURNALIST_LICENSE_KEY: ${{ secrets.COJOURNALIST_LICENSE_KEY }}
        run: |
          if [ -z "$COJOURNALIST_LICENSE_KEY" ]; then
            echo "::error::COJOURNALIST_LICENSE_KEY secret not set"
            echo "Set it with: gh secret set COJOURNALIST_LICENSE_KEY"
            exit 1
          fi

          HTTP_CODE=$(curl -s -X POST -o /tmp/license_response.json -w "%{http_code}" \
            -H "Content-Type: application/json" \
            -d "{\"key\": \"${COJOURNALIST_LICENSE_KEY}\"}" \
            "https://www.cojournalist.ai/api/license/validate" \
            --max-time 10 2>/dev/null || echo "000")

          if [ "$HTTP_CODE" = "200" ]; then
            echo "License valid"
            cat /tmp/license_response.json
            echo "valid=true" >> $GITHUB_OUTPUT
          elif [ "$HTTP_CODE" = "403" ]; then
            echo "::error::License invalid or expired"
            cat /tmp/license_response.json
            exit 1
          else
            # Endpoint unreachable -- allow grace period (fail open)
            echo "::warning::License server unreachable (HTTP $HTTP_CODE). Proceeding with grace period."
            echo "valid=grace" >> $GITHUB_OUTPUT
          fi

      # -------------------------------------------------------------------
      # Step 2: Checkout the fork
      # -------------------------------------------------------------------
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      # -------------------------------------------------------------------
      # Step 3: Fetch and merge upstream
      # -------------------------------------------------------------------
      - name: Configure git
        run: |
          git config user.name "coJournalist Sync Bot"
          git config user.email "sync@cojournalist.ai"

      - name: Add upstream remote
        run: |
          git remote add upstream https://github.com/buriedsignals/cojournalist-os.git || true
          git fetch upstream main

      - name: Detect new migrations before merge
        id: migrations
        run: |
          # List migration files that exist upstream but not in our branch
          NEW_MIGRATIONS=$(git diff --name-only HEAD upstream/main -- supabase/migrations/ | sort)

          if [ -n "$NEW_MIGRATIONS" ]; then
            echo "New migrations detected:"
            echo "$NEW_MIGRATIONS"
            echo "has_new_migrations=true" >> $GITHUB_OUTPUT
            echo "migration_files<<EOF" >> $GITHUB_OUTPUT
            echo "$NEW_MIGRATIONS" >> $GITHUB_OUTPUT
            echo "EOF" >> $GITHUB_OUTPUT
          else
            echo "No new migrations"
            echo "has_new_migrations=false" >> $GITHUB_OUTPUT
          fi

      - name: Merge upstream
        run: |
          git merge upstream/main --no-edit -m "sync: merge upstream $(date -u +%Y-%m-%d)"

      - name: Push merged changes
        run: |
          git push origin main

      # -------------------------------------------------------------------
      # Step 4: Run new migrations (if any)
      # -------------------------------------------------------------------
      - name: Run new migrations
        if: steps.migrations.outputs.has_new_migrations == 'true'
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
          SUPABASE_PROJECT_REF: ${{ secrets.SUPABASE_PROJECT_REF }}
        run: |
          if [ -z "$SUPABASE_ACCESS_TOKEN" ] || [ -z "$SUPABASE_PROJECT_REF" ]; then
            echo "::warning::SUPABASE_ACCESS_TOKEN or SUPABASE_PROJECT_REF not set. Skipping automatic migration."
            echo "New migrations need manual application:"
            echo "${{ steps.migrations.outputs.migration_files }}"
            exit 0
          fi

          # Install Supabase CLI
          npm install -g supabase

          # Link to project
          supabase link --project-ref "$SUPABASE_PROJECT_REF"

          # Push migrations
          supabase db push
          echo "Migrations applied successfully"

      # -------------------------------------------------------------------
      # Step 5: Trigger deploy
      # -------------------------------------------------------------------
      - name: Trigger Render deploy
        if: success()
        env:
          RENDER_DEPLOY_HOOK: ${{ secrets.RENDER_DEPLOY_HOOK }}
        run: |
          if [ -n "$RENDER_DEPLOY_HOOK" ]; then
            echo "Triggering Render deploy..."
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$RENDER_DEPLOY_HOOK")
            if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
              echo "Render deploy triggered successfully"
            else
              echo "::warning::Render deploy hook returned HTTP $HTTP_CODE"
            fi
          else
            echo "No RENDER_DEPLOY_HOOK configured. If using Docker, rebuild manually:"
            echo "  cd deploy/docker && docker compose pull && docker compose up -d --build"
          fi

      # -------------------------------------------------------------------
      # Summary
      # -------------------------------------------------------------------
      - name: Summary
        run: |
          echo "## Sync Complete" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **License:** ${{ steps.license.outputs.valid }}" >> $GITHUB_STEP_SUMMARY
          echo "- **New migrations:** ${{ steps.migrations.outputs.has_new_migrations }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Merged at:** $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $GITHUB_STEP_SUMMARY
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('automation/sync-upstream.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

- [ ] **Step 3: Commit**

```bash
git add automation/sync-upstream.yml
git commit -m "feat: add sync-upstream.yml for weekly auto-updates"
```

---

## Task 5.3: AGENT_INSTRUCTIONS.md

**Files:**
- Create: `automation/AGENT_INSTRUCTIONS.md`

Prompt optimized for Claude Code / Codex. Step-by-step instructions the AI agent follows to deploy coJournalist for a newsroom.

- [ ] **Step 1: Create `automation/AGENT_INSTRUCTIONS.md`**

```markdown
# coJournalist Deployment Agent Instructions

You are deploying coJournalist, an AI-powered local news monitoring platform, for a newsroom. Follow these instructions step-by-step. Ask the user for input when needed.

## Prerequisites

Before starting, confirm the user has:
1. A coJournalist license key (starts with `cjl_`)
2. A GitHub account with the `gh` CLI installed and authenticated
3. API keys for: Gemini, Firecrawl, Resend, Apify (required), MapTiler and OpenRouter (optional)
4. A Supabase account (https://supabase.com) OR Docker installed for self-hosting
5. A Render account (https://render.com) OR Docker for self-hosting

If any prerequisite is missing, help them set it up before proceeding.

## Step 1: Validate License Key

Ask the user for their license key, then validate it:

```bash
export COJOURNALIST_LICENSE_KEY="<user's key>"

curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"key\": \"${COJOURNALIST_LICENSE_KEY}\"}" \
  "https://www.cojournalist.ai/api/license/validate"
```

Expected response: `{"valid": true, "status": "active", ...}`

If the response is `403`, tell the user their key is invalid or expired and direct them to https://www.cojournalist.ai/license.

If the endpoint is unreachable, proceed anyway (fail open policy).

## Step 2: Fork the Repository

```bash
gh repo fork buriedsignals/cojournalist-os --clone
cd cojournalist-os
git remote add upstream https://github.com/buriedsignals/cojournalist-os.git
```

## Step 3: Set Up Supabase

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

## Step 4: Collect API Keys

Ask the user for each API key. Present them one at a time with the signup URL:

| Key | Service | Signup URL |
|-----|---------|------------|
| `GEMINI_API_KEY` | Google Gemini (LLM + embeddings) | https://aistudio.google.com |
| `FIRECRAWL_API_KEY` | Firecrawl (web scraping) | https://www.firecrawl.dev |
| `RESEND_API_KEY` | Resend (email) | https://resend.com |
| `APIFY_API_TOKEN` | Apify (social scraping) | https://www.apify.com |
| `PUBLIC_MAPTILER_API_KEY` | MapTiler (geocoding, optional) | https://www.maptiler.com |
| `OPENROUTER_API_KEY` | OpenRouter (alt LLMs, optional) | https://openrouter.ai |

## Step 5: Write Configuration

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

## Step 6: Deploy

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

## Step 7: Install Sync Action

```bash
# Copy the sync workflow to the fork
mkdir -p .github/workflows
cp automation/sync-upstream.yml .github/workflows/sync-upstream.yml

# Set the license key as a secret
echo "${COJOURNALIST_LICENSE_KEY}" | gh secret set COJOURNALIST_LICENSE_KEY

# If using Render, set the deploy hook
# gh secret set RENDER_DEPLOY_HOOK  (ask user for the URL from Render dashboard)

# Commit and push
git add .github/workflows/sync-upstream.yml
git commit -m "ci: install sync-upstream action"
git push origin main
```

## Step 8: Verify

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
```

- [ ] **Step 2: Commit**

```bash
git add automation/AGENT_INSTRUCTIONS.md
git commit -m "docs: add AI agent deployment instructions for Claude Code / Codex"
```

---

## Task 5.4: Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Verify file structure**

```bash
ls automation/setup.sh
ls automation/sync-upstream.yml
ls automation/AGENT_INSTRUCTIONS.md
```

All three files should exist.

- [ ] **Step 2: Verify setup.sh syntax**

```bash
bash -n automation/setup.sh && echo "setup.sh syntax OK"
```

Expected: `setup.sh syntax OK`

- [ ] **Step 3: Verify setup.sh is executable**

```bash
test -x automation/setup.sh && echo "setup.sh is executable" || echo "setup.sh is NOT executable"
```

Expected: `setup.sh is executable`

- [ ] **Step 4: Verify sync-upstream.yml syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('automation/sync-upstream.yml'))" && echo "sync-upstream.yml YAML valid"
```

Expected: `sync-upstream.yml YAML valid`

- [ ] **Step 5: Verify license validation is present in both scripts**

```bash
# setup.sh must contain license validation
grep -c "license/validate" automation/setup.sh
```

Expected: `1` (one occurrence in the LICENSE_API variable or curl call)

```bash
# sync-upstream.yml must contain license validation
grep -c "license/validate" automation/sync-upstream.yml
```

Expected: `1`

- [ ] **Step 6: Verify setup.sh covers all 10 documented steps**

From the spec (Section 8), setup.sh should:
1. Validate license key -- check for `validate_license`
2. Fork the OS repo -- check for `fork_repo`
3. Collect API keys -- check for `collect_api_keys`
4. Initialize Supabase -- check for `setup_supabase`
5. Run migrations -- check for `db push` or `psql`
6. Deploy Edge Functions -- check for `functions deploy`
7. Write `.env` -- check for `write_env_file`
8. Deploy to Render or Docker -- check for `deploy`
9. Install sync action -- check for `install_sync_action`
10. Health check -- check for `health_check`

```bash
for func in validate_license fork_repo collect_api_keys setup_supabase write_env_file deploy install_sync_action health_check; do
    if grep -q "$func" automation/setup.sh; then
        echo "OK: $func"
    else
        echo "MISSING: $func"
    fi
done
```

Expected: All show `OK`.

- [ ] **Step 7: Verify sync-upstream.yml covers all documented steps**

From the spec (Section 8), sync-upstream.yml should:
1. Validate license key
2. Fetch upstream changes
3. Merge upstream
4. Detect new migrations
5. Run migrations
6. Trigger deploy

```bash
for keyword in "Validate License" "upstream main" "Merge upstream" "migrations" "Trigger Render"; do
    if grep -q "$keyword" automation/sync-upstream.yml; then
        echo "OK: $keyword"
    else
        echo "MISSING: $keyword"
    fi
done
```

Expected: All show `OK`.

- [ ] **Step 8: Verify AGENT_INSTRUCTIONS.md covers all steps**

```bash
for step in "Validate License" "Fork" "Supabase" "API Keys" "Configuration" "Deploy" "Sync Action" "Verify"; do
    if grep -qi "$step" automation/AGENT_INSTRUCTIONS.md; then
        echo "OK: $step"
    else
        echo "MISSING: $step"
    fi
done
```

Expected: All show `OK`.

- [ ] **Step 9: Verify fail-open policy is implemented**

Both scripts must proceed on network errors (HTTP 000) and exit on explicit rejection (HTTP 403):

```bash
# setup.sh: check for grace period on 000
grep -A2 '"000"' automation/setup.sh | head -3
```

Expected: Contains "grace period" or "Proceeding"

```bash
# sync-upstream.yml: check for grace period
grep -A2 'unreachable' automation/sync-upstream.yml | head -3
```

Expected: Contains "grace" or "Proceeding"

- [ ] **Step 10: Commit milestone**

```bash
git commit --allow-empty -m "milestone: Phase 5 complete -- automation scripts ready"
```

---

## Task Dependency Graph

```
5.1 (setup.sh) ─────────────┐
                             │
5.2 (sync-upstream.yml) ─────┤── 5.4 (verification)
                             │
5.3 (AGENT_INSTRUCTIONS.md) ─┘
```

Tasks 5.1, 5.2, and 5.3 can run in parallel -- they are independent files with no code dependencies between them. Task 5.4 depends on all three.
