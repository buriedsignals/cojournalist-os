#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: automation/adopt-signup-allowlist.sh --domain <domain> --admin <email> [--project-ref <ref>] [--dry-run]

Seeds the upstream public.signup_email_allowlist table without truncating
existing entries. Real execution uses the Supabase REST API with a service-role
key resolved from SUPABASE_SERVICE_ROLE_KEY or from the Supabase CLI.
EOF
}

DOMAIN=""
ADMIN_EMAIL=""
PROJECT_REF=""
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --domain)
      DOMAIN="${2:-}"
      shift 2
      ;;
    --admin)
      ADMIN_EMAIL="${2:-}"
      shift 2
      ;;
    --project-ref)
      PROJECT_REF="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

lower() { printf "%s" "$1" | tr '[:upper:]' '[:lower:]'; }
sql_quote() { printf "%s" "$1" | sed "s/'/''/g"; }

DOMAIN="$(lower "${DOMAIN#@}")"
ADMIN_EMAIL="$(lower "$ADMIN_EMAIL")"

if [ -z "$DOMAIN" ]; then
  echo "--domain is required." >&2
  exit 2
fi

if [ -z "$ADMIN_EMAIL" ]; then
  echo "--admin is required." >&2
  exit 2
fi

if ! [[ "$DOMAIN" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$ ]]; then
  echo "Invalid domain: $DOMAIN" >&2
  exit 2
fi

if ! [[ "$ADMIN_EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
  echo "Invalid admin email: $ADMIN_EMAIL" >&2
  exit 2
fi

if [ -z "$PROJECT_REF" ] && [ -f "supabase/.temp/project-ref" ]; then
  PROJECT_REF="$(cat supabase/.temp/project-ref)"
fi

if [ -z "$PROJECT_REF" ]; then
  echo "No Supabase project ref found. Pass --project-ref <ref> or run supabase link first." >&2
  exit 2
fi

SQL="insert into public.signup_email_allowlist (kind, value, reason)
values
  ('email', '$(sql_quote "$ADMIN_EMAIL")', 'initial admin'),
  ('domain', '$(sql_quote "$DOMAIN")', 'newsroom signup domain')
on conflict (kind, value) do update
set reason = excluded.reason,
    updated_at = now();"

if [ "$DRY_RUN" -eq 1 ]; then
  printf "%s\n" "$SQL"
  printf "\nAfter the rows exist, set supabase/config.toml to:\n"
  printf "[auth.hook.before_user_created]\n"
  printf "enabled = true\n"
  printf "uri = \"pg-functions://postgres/public/hook_restrict_signup_by_allowlist\"\n"
  printf "\nThen run:\n"
  printf "supabase config push --project-ref %s\n" "$PROJECT_REF"
  exit 0
fi

if ! command -v supabase >/dev/null 2>&1; then
  echo "Supabase CLI is required. Install it and re-run this script." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

SUPABASE_URL="${SUPABASE_URL:-https://${PROJECT_REF}.supabase.co}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY:-}}"

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required to read the service-role key from Supabase CLI output." >&2
    echo "Alternatively export SUPABASE_SERVICE_ROLE_KEY and re-run this script." >&2
    exit 1
  fi

  KEYS_JSON="$(supabase projects api-keys --project-ref "$PROJECT_REF" -o json)"
  SUPABASE_SERVICE_ROLE_KEY="$(printf "%s" "$KEYS_JSON" | jq -r '.[] | select((.name // .key_name // "") | test("service"; "i")) | .api_key // .key // empty' | head -1)"
fi

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo "Could not resolve Supabase service-role key." >&2
  echo "Run supabase login or export SUPABASE_SERVICE_ROLE_KEY, then re-run this script." >&2
  exit 1
fi

BODY='[
  {"kind":"email","value":"'"$ADMIN_EMAIL"'","reason":"initial admin"},
  {"kind":"domain","value":"'"$DOMAIN"'","reason":"newsroom signup domain"}
]'

TMP_BODY="$(mktemp)"
HTTP_CODE="$(curl -sS -o "$TMP_BODY" -w "%{http_code}" \
  -X POST "${SUPABASE_URL%/}/rest/v1/signup_email_allowlist?on_conflict=kind,value" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: resolution=merge-duplicates,return=minimal" \
  --data "$BODY")"

if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 300 ]; then
  echo "Allowlist upsert failed with HTTP $HTTP_CODE." >&2
  sed 's/^/  /' "$TMP_BODY" >&2
  rm -f "$TMP_BODY"
  exit 1
fi
rm -f "$TMP_BODY"

printf "Seeded signup allowlist for %s and %s.\n" "$ADMIN_EMAIL" "$DOMAIN"
printf "\nNext, set supabase/config.toml to:\n"
printf "[auth.hook.before_user_created]\n"
printf "enabled = true\n"
printf "uri = \"pg-functions://postgres/public/hook_restrict_signup_by_allowlist\"\n"
printf "\nThen run:\n"
printf "supabase config push --project-ref %s\n" "$PROJECT_REF"
