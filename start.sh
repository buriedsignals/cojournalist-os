#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-saas}"

usage() {
	cat <<'USAGE'
Usage:
  ./start.sh [saas]      Start Docker backend + Docker frontend on http://localhost:5173
  ./start.sh oss-demo   Start local Supabase demo frontend on http://localhost:4173

The canonical private-repo daily workflow is still:
  cd frontend && npm run dev
USAGE
}

die() {
	echo "Error: $*" >&2
	exit 1
}

read_env_var() {
	local key="$1"
	local line value
	line="$(grep -E "^(export[[:space:]]+)?${key}=" "$ROOT_DIR/.env" 2>/dev/null | tail -n 1 || true)"
	value="${line#*=}"
	value="${value%%[[:space:]]#*}"
	value="${value%\"}"
	value="${value#\"}"
	value="${value%\'}"
	value="${value#\'}"
	printf '%s' "$value"
}

env_value() {
	local key="$1"
	local current="${!key:-}"
	if [[ -n "$current" ]]; then
		printf '%s' "$current"
	else
		read_env_var "$key"
	fi
}

require_env() {
	local key="$1"
	if [[ -z "$(env_value "$key")" ]]; then
		die "Missing required local SaaS env key: $key"
	fi
}

check_docker() {
	if ! docker info >/dev/null 2>&1; then
		die "Docker is not running."
	fi
}

compose() {
	if docker compose version >/dev/null 2>&1; then
		docker compose "$@"
	elif command -v docker-compose >/dev/null 2>&1; then
		docker-compose "$@"
	else
		die "Docker Compose is not installed."
	fi
}

start_saas() {
	cd "$ROOT_DIR"
	[[ -f .env ]] || die ".env file not found. Copy .env.example to .env and fill in local SaaS credentials."
	check_docker

	require_env MUCKROCK_CLIENT_ID
	require_env MUCKROCK_CLIENT_SECRET
	require_env SESSION_SECRET
	require_env SUPABASE_URL
	require_env SUPABASE_ANON_KEY

	local service_key service_role_key
	service_key="$(env_value SUPABASE_SERVICE_KEY)"
	service_role_key="$(env_value SUPABASE_SERVICE_ROLE_KEY)"
	if [[ -z "$service_key" && -z "$service_role_key" ]]; then
		die "Missing required local SaaS env key: SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY"
	fi

	echo "Starting coJournalist local SaaS stack..."
	echo "  Frontend: http://localhost:5173"
	echo "  Backend:  http://localhost:8000"
	echo "  Auth:     /api/auth/* proxies to the local FastAPI broker"
	echo

	compose up --build
}

start_oss_demo() {
	cd "$ROOT_DIR"
	check_docker
	command -v supabase >/dev/null 2>&1 || die "Supabase CLI is not installed."

	echo "Starting coJournalist local Supabase demo..."
	echo "  Frontend: http://localhost:4173"
	echo "  Auth:     local Supabase email/password demo"
	echo

	FRONTEND_HOST=127.0.0.1 FRONTEND_PORT=4173 FRONTEND_STRICT_PORT=true \
		bash "$ROOT_DIR/scripts/dev/run-frontend-supabase-local-demo.sh"
}

case "$MODE" in
	saas | docker | default)
		start_saas
		;;
	oss-demo)
		start_oss_demo
		;;
	-h | --help | help)
		usage
		;;
	*)
		usage >&2
		exit 1
		;;
esac
