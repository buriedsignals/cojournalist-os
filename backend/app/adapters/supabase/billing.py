"""NoOp billing adapter for self-hosted Supabase deployments.

All operations succeed unconditionally. Self-hosted newsrooms have no
credit limits -- the billing-related code in routers calls these methods,
and the adapter silently approves everything.

DEPENDS ON: ports.billing (BillingPort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

from app.ports.billing import BillingPort


class NoOpBilling(BillingPort):
    """Billing adapter that always succeeds. No credit limits."""

    async def validate_credits(self, user_id: str, operation: str) -> bool:
        """Always returns True -- no credit validation in self-hosted mode."""
        return True

    async def decrement_credit(self, user_id: str, operation: str) -> bool:
        """Always returns True -- no credit deduction in self-hosted mode."""
        return True

    async def get_balance(self, user_id: str) -> dict:
        """Returns an unlimited balance indicator.

        Returns credits=-1 as a sentinel for unlimited, with an explicit
        'unlimited' flag for frontend consumption.
        """
        return {
            "credits": -1,
            "unlimited": True,
        }
