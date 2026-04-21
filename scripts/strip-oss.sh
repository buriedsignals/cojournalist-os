#!/usr/bin/env bash
# strip-oss.sh — Strip SaaS-only code for OSS mirror
#
# Single source of truth for what gets removed/replaced.
# Called by both mirror-oss.yml (production) and ci.yml (PR validation).
#
# Usage: bash scripts/strip-oss.sh
set -euo pipefail

echo "=== Stripping SaaS-only code ==="

# AWS infrastructure was removed in the v2 migration — nothing to strip here.
# (aws/ and backend/app/adapters/aws/ no longer exist in the SaaS source tree.)

# Backend: remove SaaS-only auth broker (MuckRock OAuth)
rm -f backend/app/routers/auth.py
rm -f backend/app/services/muckrock_client.py
rm -f backend/tests/unit/auth/test_auth_router.py

# main.py unconditionally mounts auth.router in the SaaS source; strip the
# import + mount for OSS since the broker depends on MuckRock credentials.
# OSS users authenticate directly with Supabase (email/password on the
# frontend /login route), not through a broker.
sed -i '/^# Auth broker/d' backend/app/main.py
sed -i '/^from app\.routers import auth$/d' backend/app/main.py
sed -i '/app\.include_router(auth\.router/d' backend/app/main.py

# NOTE: user_service.py and session_service.py are kept for OSS. Many
# routers still import them (scraper, pulse, onboarding, user, data_extractor,
# utils/credits). They're dormant under deployment_target="supabase" but
# must be importable for the non-auth surface to load. PR 4 (post-cutover
# on the SaaS side) will remove those routers + services together.

# Backend: remove SaaS-only billing and credit management
rm -f backend/app/utils/credits.py
rm -f backend/app/services/cron.py
rm -f backend/app/services/seed_data_service.py
rm -f backend/app/services/api_key_service.py

# Backend: remove admin dashboard (SaaS revenue reporting)
rm -f backend/app/routers/admin.py
rm -f backend/app/services/admin_report_service.py
rm -f backend/app/schemas/admin.py

# Backend: remove feedback router (Linear integration — SaaS-only)
rm -f backend/app/routers/feedback.py

# Backend: remove threat modeling dashboard (internal security assessment)
rm -rf backend/app/routers/threat_modeling/

# Backend: remove SaaS-only test files
rm -f backend/tests/unit/api/test_admin.py
rm -f backend/tests/unit/shared/test_admin_report.py

# -------------------------------------------------------------------
# CI/CD: remove workflows that reference the dev repo
# -------------------------------------------------------------------
rm -f .github/workflows/mirror-*.yml
rm -f .github/workflows/claude*.yml
# CLI release workflow depends on Apple signing secrets that only exist on
# the private monorepo. OSS forks can restore this and add their own secrets.
rm -f .github/workflows/cli-release.yml

# -------------------------------------------------------------------
# Docs: remove internal/SaaS-specific documentation
# -------------------------------------------------------------------
rm -rf docs/superpowers/
rm -rf docs/muckrock/
rm -rf docs/billing/
rm -rf docs/benchmarks/
rm -rf docs/research/
rm -f docs/architecture/license-key-infrastructure.md
rm -f docs/architecture/aws-architecture.md
rm -f docs/architecture/records-and-deduplication.md
rm -f docs/v2-migration-runbook.md
rm -rf .firecrawl/

# -------------------------------------------------------------------
# Scripts: keep the OSS-friendly smoke test; drop the one-time SaaS
# migration tooling (pulls DynamoDB via MuckRock-issued IAM creds).
# -------------------------------------------------------------------
rm -rf scripts/migrate/

# -------------------------------------------------------------------
# Premium automation & deploy configs (license-gated)
# -------------------------------------------------------------------
rm -f automation/SETUP_AGENT.md
rm -f automation/setup.sh
rm -f automation/sync-upstream.yml
rm -f deploy/render/render.yaml
rm -f deploy/SETUP.md

# -------------------------------------------------------------------
# Frontend: replace auth system (MuckRock OAuth → Supabase Auth)
# -------------------------------------------------------------------
printf '%s\n' \
  '/**' \
  ' * Auth Store — Supabase Auth (self-hosted deployment).' \
  ' *' \
  ' * Re-exports from auth-supabase for email/password authentication.' \
  ' *' \
  " * USED BY: All components that import from '\$lib/stores/auth'" \
  ' */' \
  "import * as supabase from './auth-supabase';" \
  '' \
  'export const authStore = supabase.authStore;' \
  'export const currentUser = supabase.currentUser;' \
  'export const auth = supabase.auth;' \
  > frontend/src/lib/stores/auth.ts

rm -f frontend/src/lib/stores/auth-muckrock.ts

# -------------------------------------------------------------------
# Frontend: /login is now shared SaaS+OSS (single route, dual-path
# rendered based on PUBLIC_DEPLOYMENT_TARGET). OSS build sets that to
# "supabase" and the MuckRock button is hidden at render time. Commit
# 839e23d collapsed /login-supabase into /login deliberately.
# No rename needed here.
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# Frontend: strip SaaS-only routes and references
# -------------------------------------------------------------------
rm -rf frontend/src/routes/admin/
rm -rf frontend/src/routes/pricing/
rm -rf frontend/src/routes/terms/

sed -i "s|'/login', '/pricing', '/setup', '/terms'|'/login', '/setup'|" frontend/src/routes/+layout.svelte
sed -i 's|href="/pricing"|href="/"|' frontend/src/routes/setup/+page.svelte
sed -i "s#\$page.url.pathname === '/pricing' || ##" frontend/src/lib/components/ui/MobileBlocker.svelte
sed -i "s|goto('/pricing');|return; // unlimited in self-hosted|" frontend/src/lib/components/workspace/NewScoutDropdown.svelte
sed -i "s|https://accounts.muckrock.com/[^']*|#|g" frontend/src/lib/components/modals/PreferencesModal.svelte
# Remove UpgradeModal and all credit-gating logic (no credits in OSS)
rm -f frontend/src/lib/components/modals/UpgradeModal.svelte

# Strip UpgradeModal imports from components that reference it
sed -i "/import UpgradeModal/d" frontend/src/lib/components/feed/FeedView.svelte
sed -i "/import UpgradeModal/d" frontend/src/lib/components/panels/ScoutsPanel.svelte
sed -i "/import UpgradeModal/d" frontend/src/lib/components/modals/ScoutScheduleModal.svelte
sed -i "/import UpgradeModal/d" frontend/src/lib/components/sidebars/DataExtract.svelte

# Strip showUpgradeModal state and credit gate blocks
sed -i "/let showUpgradeModal/d" frontend/src/lib/components/feed/FeedView.svelte
sed -i "/let showUpgradeModal/d" frontend/src/lib/components/panels/ScoutsPanel.svelte
sed -i "/let showUpgradeModal/d" frontend/src/lib/components/modals/ScoutScheduleModal.svelte
sed -i "/let showUpgradeModal/d" frontend/src/lib/components/sidebars/DataExtract.svelte

# Strip <UpgradeModal .../> component blocks (multi-line: delete from <UpgradeModal to />)
sed -i '/<UpgradeModal/,/\/>/d' frontend/src/lib/components/feed/FeedView.svelte
sed -i '/<UpgradeModal/,/\/>/d' frontend/src/lib/components/panels/ScoutsPanel.svelte
sed -i '/<UpgradeModal/,/\/>/d' frontend/src/lib/components/modals/ScoutScheduleModal.svelte
sed -i '/<UpgradeModal/,/\/>/d' frontend/src/lib/components/sidebars/DataExtract.svelte

# Replace credit gates with unlimited (credits ?? 0 → 999999)
sed -i 's/\$authStore\.user?\.credits ?? 0/999999/g' frontend/src/lib/components/feed/FeedView.svelte
sed -i 's/\$authStore\.user?\.credits ?? 0/999999/g' frontend/src/lib/components/panels/ScoutsPanel.svelte
sed -i 's/\$authStore\.user?\.credits ?? 0/999999/g' frontend/src/lib/components/modals/ScoutScheduleModal.svelte
sed -i 's/\$authStore\.user?\.credits ?? 0/999999/g' frontend/src/lib/components/sidebars/DataExtract.svelte

# Frontend: remove FeedbackModal and BugReportButton (Linear integration — SaaS-only)
rm -f frontend/src/lib/components/modals/FeedbackModal.svelte
sed -i "/import BugReportButton from/d" frontend/src/routes/+layout.svelte
sed -i "/import FeedbackModal from/d" frontend/src/routes/+layout.svelte
sed -i "/let feedbackModalOpen/d" frontend/src/routes/+layout.svelte
sed -i "/BugReportButton/d" frontend/src/routes/+layout.svelte
sed -i "/FeedbackModal/d" frontend/src/routes/+layout.svelte

# Backend: strip feedback router import and mount from main.py
sed -i '/^    feedback,$/d' backend/app/main.py
sed -i '/feedback\.router/d' backend/app/main.py

# -------------------------------------------------------------------
# Frontend: strip leftover MuckRock + /pricing references from shared
# files that dual-serve SaaS and OSS. These are SaaS-facing UI fragments
# that are gated behind PUBLIC_DEPLOYMENT_TARGET at runtime, but the
# grep-based validator below can't see runtime flags — it only sees
# strings. Strip them from OSS source.
# -------------------------------------------------------------------

# docs/+page.svelte: pricing links + MuckRock mention in prose
sed -i 's|<a href="/pricing">|<a href="#">|g' frontend/src/routes/docs/+page.svelte
sed -i 's|href="/pricing"|href="#"|g' frontend/src/routes/docs/+page.svelte
sed -i 's|sign in with MuckRock OAuth\. Free tier starts with 100 credits/month\.|sign in with your email address.|' frontend/src/routes/docs/+page.svelte

# +page.svelte (home/workspace): credits-pill + user-menu pricing links
sed -i 's|href="/pricing"|href="/"|g' frontend/src/routes/+page.svelte

# login/+page.svelte: remove the entire MuckRock-preview branch + "See pricing" CTAs
# The {#if PUBLIC_DEPLOYMENT_TARGET === 'supabase' && !previewMuckRock} block shows
# the email/password form (OSS path); the {:else} branch shows the MuckRock button
# (SaaS path). For OSS we remove the SaaS branch entirely.
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("frontend/src/routes/login/+page.svelte")
src = p.read_text()
# Drop the previewMuckRock state (dev-only toggle)
src = re.sub(r"\n\s*// Dev-only:.*?previewMuckRock.*?\n", "\n", src, count=1, flags=re.DOTALL)
src = re.sub(r"\n\s*let previewMuckRock\s*=\s*false;\s*", "\n", src, count=1)
# Replace `!previewMuckRock && auth.login()` → just open supabase flow fallback
src = src.replace("!previewMuckRock && auth.login()", "auth.login()")
# Strip the `&& !previewMuckRock` clause wherever it still lingers (e.g. inside
# `{#if PUBLIC_DEPLOYMENT_TARGET === 'supabase' && !previewMuckRock}`).
src = src.replace(" && !previewMuckRock", "")
src = src.replace("!previewMuckRock && ", "")
# Drop any remaining `previewMuckRock` identifier references.
src = re.sub(r"\bpreviewMuckRock\b", "false", src)
# Drop "See pricing" CTA links — both occurrences
src = re.sub(r'<a href="/pricing"[^>]*>[^<]*</a>', '', src)
# Strip the MuckRock-preview checkbox/label (entire <label class="muckrock-toggle">...</label>)
src = re.sub(r'<label class="muckrock-toggle">.*?</label>', '', src, flags=re.DOTALL)
# Strip the MuckRock preview text comment lines
src = re.sub(r'<p class="auth-subtitle">Sign in via MuckRock</p>', '<p class="auth-subtitle">Sign in</p>', src)
src = src.replace("Sign in with MuckRock", "Sign in")
# Strip muckrock-toggle CSS rules
src = re.sub(r'\.muckrock-toggle\s*\{[^}]*\}', '', src)
src = re.sub(r'\.muckrock-toggle\s+input\s*\{[^}]*\}', '', src)
src = re.sub(r'\.muckrock-toggle:hover\s*\{[^}]*\}', '', src)
p.write_text(src)
PY

# api-client.ts: strip MuckRock JSDoc comments (comment-only references)
sed -i "s|, '' for MuckRock cookies|, '' for self-hosted|g" frontend/src/lib/api-client.ts
sed -i "s|for MuckRock session-cookie auth|for legacy session-cookie auth|g" frontend/src/lib/api-client.ts
sed -i "s|MuckRock||g" frontend/src/lib/api-client.ts

# -------------------------------------------------------------------
# Validate: no SaaS-only references remain
# -------------------------------------------------------------------
echo "=== Validating OSS build ==="
FAIL=0

if grep -ri "muckrock" --exclude="auth-supabase.ts" --exclude="types.ts" --exclude="PreferencesModal.svelte" --exclude-dir="faq" --exclude-dir="paraglide" frontend/src/ 2>/dev/null; then
  echo "ERROR: MuckRock references found in OSS build"
  FAIL=1
fi

if grep -rE "'/pricing'|\"/pricing\"" frontend/src/ 2>/dev/null; then
  echo "ERROR: /pricing references found in OSS build"
  FAIL=1
fi

if grep -r "accounts.muckrock.com" frontend/src/ 2>/dev/null; then
  echo "ERROR: accounts.muckrock.com URLs found in OSS build"
  FAIL=1
fi

if grep -r "auth-muckrock" --exclude="auth-supabase.ts" frontend/src/ 2>/dev/null; then
  echo "ERROR: auth-muckrock references found in OSS build"
  FAIL=1
fi

if [ -d "backend/app/routers/threat_modeling" ]; then
  echo "ERROR: threat_modeling directory found in OSS build"
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo "Fix: update scripts/strip-oss.sh with additional sed commands"
  exit 1
fi

echo "=== OSS strip complete — all validations passed ==="
