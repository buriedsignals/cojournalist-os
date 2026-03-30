"""Supabase implementation of RunStoragePort.

Uses asyncpg to execute SQL against the PostgreSQL scout_runs table.

DEPENDS ON: connection (get_pool), ports.storage (RunStoragePort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.adapters.supabase.connection import get_pool
from app.adapters.supabase.utils import row_to_dict
from app.ports.storage import RunStoragePort

logger = logging.getLogger(__name__)


class SupabaseRunStorage(RunStoragePort):
    """PostgreSQL-backed scout run storage using asyncpg."""

    def __init__(self):
        self.pool = None

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def store_run(self, scout_id: str, user_id: str, status: str,
                        error_message: str = None, **kwargs) -> dict:
        """Insert a new scout run record."""
        await self._ensure_pool()

        completed_at = None
        if status in ("success", "error", "skipped"):
            completed_at = datetime.now(timezone.utc)

        row = await self.pool.fetchrow(
            """
            INSERT INTO scout_runs (
                scout_id, user_id, status, error_message,
                scraper_status, criteria_status, notification_sent,
                articles_count, completed_at
            )
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            scout_id,
            user_id,
            status,
            error_message,
            kwargs.get("scraper_status", False),
            kwargs.get("criteria_status", False),
            kwargs.get("notification_sent", False),
            kwargs.get("articles_count", 0),
            completed_at,
        )
        return row_to_dict(row)

    async def get_latest_runs(self, user_id: str, limit: int = 10) -> list[dict]:
        """Get the most recent runs for a user across all scouts."""
        await self._ensure_pool()
        rows = await self.pool.fetch(
            """
            SELECT * FROM scout_runs
            WHERE user_id = $1::uuid
            ORDER BY started_at DESC
            LIMIT $2
            """,
            user_id, limit,
        )
        return [row_to_dict(row) for row in rows]

    async def get_latest_run_for_scout(self, scout_id: str) -> Optional[dict]:
        """Get the most recent run for a specific scout."""
        await self._ensure_pool()
        row = await self.pool.fetchrow(
            """
            SELECT * FROM scout_runs
            WHERE scout_id = $1::uuid
            ORDER BY started_at DESC
            LIMIT 1
            """,
            scout_id,
        )
        return row_to_dict(row)

    async def delete_runs_for_scout(self, user_id: str, scout_name: str) -> None:
        """Delete all runs for a scout. Even though CASCADE handles this when
        the scout is deleted, the port requires this method for cases where
        runs are cleaned up independently (e.g., scout reset)."""
        await self._ensure_pool()
        await self.pool.execute(
            """
            DELETE FROM scout_runs
            WHERE scout_id IN (
                SELECT id FROM scouts WHERE user_id = $1::uuid AND name = $2
            )
            """,
            user_id, scout_name,
        )
