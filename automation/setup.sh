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
