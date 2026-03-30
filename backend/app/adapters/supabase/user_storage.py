"""Supabase implementation of UserStoragePort.

Uses asyncpg to execute SQL against the PostgreSQL user_preferences table.

DESIGN NOTE: UserStoragePort defines 16 methods including credit/billing and org/team
operations from the SaaS version. The self-hosted OSS version doesn't use credits or
team orgs, so this adapter implements them as follows:
  - get_user, create_or_update_user, update_profile, get_cms_config: Real SQL
  - Credit methods (get_balance, create_credits, update_credits, decrement_credits):
    Return success/unlimited (mirrors NoOpBilling -- self-hosted has no limits)
  - Org/team methods (create_org, get_org_credits, get_org_balance, decrement_org_credits,
    update_org_credits, claim_seat, cancel_team_org): Raise NotImplementedError
    because team features require MuckRock entitlements not available in self-hosted mode

DEPENDS ON: connection (get_pool), ports.storage (UserStoragePort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.adapters.supabase.connection import get_pool
from app.adapters.supabase.utils import row_to_dict
from app.ports.storage import UserStoragePort

logger = logging.getLogger(__name__)

# Fields that can be set on user_preferences
USER_FIELDS = [
    "timezone", "preferred_language", "notification_email",
    "default_location", "excluded_domains", "cms_api_url",
    "cms_api_token", "preferences", "onboarding_completed",
    "onboarding_tour_completed",
]


def _user_row_to_dict(row) -> dict | None:
    """Convert user_preferences row. Returns None for None (not found)."""
    if row is None:
        return None
    return row_to_dict(row, uuid_fields=("user_id",))


class SupabaseUserStorage(UserStoragePort):
    """PostgreSQL-backed user preference storage using asyncpg."""

    def __init__(self):
        self.pool = None

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def get_user(self, user_id: str) -> dict | None:
        """Get user preferences. Returns None if not found."""
        await self._ensure_pool()

        row = await self.pool.fetchrow(
            "SELECT * FROM user_preferences WHERE user_id = $1::uuid",
            user_id,
        )
        return _user_row_to_dict(row)

    async def create_or_update_user(self, user_id: str, data: dict) -> dict:
        """Create or update user preferences using UPSERT.

        On conflict (user already exists), updates the provided fields.
        """
        await self._ensure_pool()

        # Build columns and values from provided data
        columns = ["user_id"]
        placeholders = ["$1::uuid"]
        values: list = [user_id]
        update_clauses = []
        idx = 2

        for field in USER_FIELDS:
            if field in data:
                columns.append(field)
                value = data[field]
                if field in ("default_location", "preferences") and isinstance(value, dict):
                    value = json.dumps(value)
                placeholders.append(f"${idx}")
                update_clauses.append(f"{field} = EXCLUDED.{field}")
                values.append(value)
                idx += 1

        if not update_clauses:
            # Nothing to update, just ensure the row exists
            update_clauses = ["updated_at = NOW()"]

        sql = f"""
            INSERT INTO user_preferences ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (user_id) DO UPDATE SET
                {', '.join(update_clauses)}
            RETURNING *
        """
        row = await self.pool.fetchrow(sql, *values)
        return _user_row_to_dict(row)

    async def update_profile(self, user_id: str, updates: dict) -> None:
        """Update specific user profile fields."""
        await self._ensure_pool()

        if not updates:
            return

        set_clauses = []
        values = []
        idx = 1

        for field, value in updates.items():
            if field in USER_FIELDS:
                if field in ("default_location", "preferences") and isinstance(value, dict):
                    value = json.dumps(value)
                set_clauses.append(f"{field} = ${idx}")
                values.append(value)
                idx += 1

        if not set_clauses:
            return

        values.append(user_id)
        sql = f"""
            UPDATE user_preferences
            SET {', '.join(set_clauses)}
            WHERE user_id = ${idx}::uuid
        """
        await self.pool.execute(sql, *values)

    async def get_cms_config(self, user_id: str) -> dict:
        """Get CMS export configuration for a user."""
        await self._ensure_pool()
        row = await self.pool.fetchrow(
            "SELECT cms_api_url, cms_api_token FROM user_preferences WHERE user_id = $1::uuid",
            user_id,
        )
        if row is None:
            return {"cms_api_url": None, "cms_api_token": None}
        return dict(row)

    # ------------------------------------------------------------------
    # Credit methods -- self-hosted has no limits, mirrors NoOpBilling
    # ------------------------------------------------------------------

    async def get_balance(self, user_id: str) -> int:
        """Self-hosted: always return unlimited credits."""
        return -1  # Sentinel for unlimited

    async def create_credits(self, user_id: str, monthly_cap: int, tier: str, update_on: str | None = None) -> None:
        """Self-hosted: no-op (no credit tracking)."""
        pass

    async def update_credits(self, user_id: str, updates: dict) -> None:
        """Self-hosted: no-op (no credit tracking)."""
        pass

    async def decrement_credits(self, user_id: str, amount: int) -> bool:
        """Self-hosted: always succeeds (no credit limits)."""
        return True

    # ------------------------------------------------------------------
    # Org/team methods -- not available in self-hosted mode
    # ------------------------------------------------------------------

    async def create_org(self, org_id: str, monthly_cap: int,
                         update_on: str | None, org_name: str) -> None:
        raise NotImplementedError("Team features not available in self-hosted mode")

    async def get_org_credits(self, org_id: str) -> dict | None:
        raise NotImplementedError("Team features not available in self-hosted mode")

    async def get_org_balance(self, org_id: str) -> int:
        raise NotImplementedError("Team features not available in self-hosted mode")

    async def decrement_org_credits(self, org_id: str, amount: int) -> bool:
        raise NotImplementedError("Team features not available in self-hosted mode")

    async def update_org_credits(self, org_id: str, new_cap: int, new_update_on: str) -> None:
        raise NotImplementedError("Team features not available in self-hosted mode")

    async def claim_seat(self, org_id: str, user_id: str, tier_before_team: str) -> bool:
        raise NotImplementedError("Team features not available in self-hosted mode")

    async def cancel_team_org(self, org_id: str) -> None:
        raise NotImplementedError("Team features not available in self-hosted mode")
