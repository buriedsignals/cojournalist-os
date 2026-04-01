#!/usr/bin/env bash
# strip-oss.sh — Strip SaaS-only code for OSS mirror
#
# Single source of truth for what gets removed/replaced.
# Called by both mirror-oss.yml (production) and ci.yml (PR validation).
#
# Usage: bash scripts/strip-oss.sh
set -euo pipefail

echo "=== Stripping SaaS-only code ==="

# -------------------------------------------------------------------
# Backend: remove AWS infrastructure
# -------------------------------------------------------------------
rm -rf aws/
rm -rf backend/app/adapters/aws/

# Backend: remove SaaS-only auth (MuckRock OAuth)
rm -f backend/app/routers/auth.py
rm -f backend/app/services/muckrock_client.py

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
rm -rf .firecrawl/

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
# Frontend: replace login page (MuckRock → Supabase email/password)
# -------------------------------------------------------------------
rm -rf frontend/src/routes/login/
mv frontend/src/routes/login-supabase/ frontend/src/routes/login/

# -------------------------------------------------------------------
# Frontend: strip SaaS-only routes and references
# -------------------------------------------------------------------
rm -rf frontend/src/routes/pricing/
rm -rf frontend/src/routes/terms/

sed -i "s|'/login', '/pricing', '/setup', '/terms'|'/login', '/setup'|" frontend/src/routes/+layout.svelte
sed -i 's|href="/pricing"|href="/"|' frontend/src/routes/setup/+page.svelte
sed -i "s#\$page.url.pathname === '/pricing' || ##" frontend/src/lib/components/ui/MobileBlocker.svelte
sed -i "s|goto('/pricing');|return; // unlimited in self-hosted|" frontend/src/lib/components/ui/NewScoutDropdown.svelte
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
