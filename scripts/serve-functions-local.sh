#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v supabase >/dev/null 2>&1; then
  echo "supabase CLI is required" >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  echo ".env is required so external secrets like APIFY_API_TOKEN can be loaded" >&2
  exit 2
fi

STATUS_ENV_FILE="$(mktemp /tmp/cojo-status-env.XXXXXX)"
RUNTIME_ENV_FILE="$(mktemp /tmp/cojo-functions-env.XXXXXX)"

cleanup() {
  rm -f "$STATUS_ENV_FILE" "$RUNTIME_ENV_FILE"
}
trap cleanup EXIT

supabase status -o env | awk '/^[A-Z_][A-Z0-9_]*=/' > "$STATUS_ENV_FILE"

# shellcheck disable=SC1090
source "$STATUS_ENV_FILE"

read_project_secret() {
  local name="$1"
  local value="${!name:-}"
  if [[ -n "$value" ]]; then
    printf '%s' "$value"
    return
  fi

  awk -F= -v key="$name" '
    $1 == key {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' .env
}

APIFY_TOKEN="$(read_project_secret APIFY_API_TOKEN)"
INTERNAL_KEY="$(read_project_secret INTERNAL_SERVICE_KEY)"

if [[ -z "$APIFY_TOKEN" ]]; then
  echo "APIFY_API_TOKEN missing from environment and .env" >&2
  exit 2
fi

{
  printf 'APIFY_API_TOKEN=%s\n' "$APIFY_TOKEN"
  if [[ -n "$INTERNAL_KEY" ]]; then
    printf 'INTERNAL_SERVICE_KEY=%s\n' "$INTERNAL_KEY"
  fi
} > "$RUNTIME_ENV_FILE"

echo "Serving functions with CLI local env + APIFY_API_TOKEN"
echo "  API_URL=${API_URL:-http://127.0.0.1:54321}"

exec supabase functions serve --no-verify-jwt --env-file "$RUNTIME_ENV_FILE"
