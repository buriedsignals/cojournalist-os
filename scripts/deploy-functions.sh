#!/usr/bin/env bash
# Deploy all v2 Edge Functions to the cojournalist cloud project.
# Pre-requisite: `supabase login` (interactive — one time).
#
#   bash scripts/deploy-functions.sh
#
set -euo pipefail

PROJECT_REF="${PROJECT_REF:-gfmdziplticfoakhrfpt}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# All v2 functions. Order doesn't matter; deploys are independent.
FUNCTIONS=(
  # CRUD + search
  projects
  scouts
  units
  entities
  reflections
  user
  ingest
  openapi-spec
  scout-templates
  civic-test
  # Scout execution pipelines
  execute-scout
  scout-web-execute
  scout-beat-execute
  civic-execute
  civic-extract-worker
  social-kickoff
  apify-callback
  apify-reconcile
  scout-health-monitor
)

# Functions that already have a [functions.X] block with verify_jwt=false in
# supabase/config.toml will carry that setting. Everything else defaults to
# verify_jwt=true. All our handlers validate auth internally, so verify_jwt
# stays off for all of them (see migration CLAUDE notes).

ok=()
fail=()

for fn in "${FUNCTIONS[@]}"; do
  printf '\n=== deploying %s ===\n' "$fn"
  if supabase functions deploy "$fn" \
       --project-ref "$PROJECT_REF" \
       --no-verify-jwt 2>&1 | tail -5; then
    ok+=("$fn")
  else
    fail+=("$fn")
  fi
done

printf '\n=== summary ===\n'
printf '  ok:     %s\n' "${#ok[@]}"
printf '  failed: %s\n' "${#fail[@]}"
if [ "${#fail[@]}" -gt 0 ]; then
  printf '\nfailed:\n'
  for f in "${fail[@]}"; do printf '  - %s\n' "$f"; done
  exit 1
fi
