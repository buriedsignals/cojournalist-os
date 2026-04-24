"""
dependencies package — re-exports all public symbols for backwards compatibility.

All existing `from app.dependencies import ...` statements continue to work
without modification. Submodules:
  - auth.py      — session cookie, service key, API key, user email
  - billing.py   — org_id lookup, credit balance, credit decrement
  - providers.py — adapter provider factories (DEPLOYMENT_TARGET-aware)
"""
from app.dependencies.auth import (
    build_user_response,
    get_current_user,
    get_optional_user,
    get_user_email,
    require_admin,
    verify_api_key,
    verify_service_key,
)
from app.dependencies.billing import (
    decrement_credit,
    get_user_credits,
    get_user_org_id,
    validate_credits,
)
from app.dependencies.providers import (
    get_auth,
    get_billing,
    get_execution_storage,
    get_run_storage,
    get_scheduler,
    get_scout_storage,
    get_unit_storage,
    get_user_storage,
)

__all__ = [
    "build_user_response",
    "get_current_user",
    "get_optional_user",
    "get_user_email",
    "verify_api_key",
    "require_admin",
    "verify_service_key",
    "decrement_credit",
    "get_user_credits",
    "get_user_org_id",
    "validate_credits",
    # Adapter providers
    "get_auth",
    "get_billing",
    "get_execution_storage",
    "get_run_storage",
    "get_scheduler",
    "get_scout_storage",
    "get_unit_storage",
    "get_user_storage",
]
