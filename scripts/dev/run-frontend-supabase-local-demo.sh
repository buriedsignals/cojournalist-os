#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"
FRONTEND_STRICT_PORT="${FRONTEND_STRICT_PORT:-true}"

cd "$ROOT_DIR"

supabase start >/dev/null
STATUS_ENV="$(supabase status -o env)"

read_status_var() {
	local key="$1"
	printf '%s\n' "$STATUS_ENV" | sed -n "s/^${key}=\"\\([^\"]*\\)\"/\\1/p" | head -n 1
}

LOCAL_SUPABASE_URL="$(read_status_var API_URL)"
LOCAL_SUPABASE_PUBLISHABLE_KEY="$(read_status_var PUBLISHABLE_KEY)"

if [[ -z "$LOCAL_SUPABASE_URL" || -z "$LOCAL_SUPABASE_PUBLISHABLE_KEY" ]]; then
	echo "Could not read local Supabase API_URL/PUBLISHABLE_KEY from 'supabase status -o env'." >&2
	exit 1
fi

cd "$FRONTEND_DIR"

export PUBLIC_DEPLOYMENT_TARGET="supabase"
export PUBLIC_MUCKROCK_ENABLED="false"
export PUBLIC_LOCAL_DEMO_MODE="true"
export PUBLIC_SUPABASE_URL="$LOCAL_SUPABASE_URL"
export PUBLIC_SUPABASE_ANON_KEY="$LOCAL_SUPABASE_PUBLISHABLE_KEY"
export VITE_API_URL="${LOCAL_SUPABASE_URL}/functions/v1"

vite_args=(--host "$FRONTEND_HOST" --port "$FRONTEND_PORT")
if [[ "$FRONTEND_STRICT_PORT" == "true" ]]; then
	vite_args+=(--strictPort)
fi

exec npm run dev:raw -- "${vite_args[@]}" "$@"
