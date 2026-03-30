"""Supabase implementation of SeenRecordStoragePort.

Uses asyncpg with INSERT ON CONFLICT DO NOTHING for idempotent mark_seen.
The UNIQUE(scout_id, signature) constraint handles dedup at the database level.

DEPENDS ON: connection (get_pool), ports.storage (SeenRecordStoragePort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import logging

from app.adapters.supabase.connection import get_pool
from app.ports.storage import SeenRecordStoragePort

logger = logging.getLogger(__name__)


class SupabaseSeenRecordStorage(SeenRecordStoragePort):
    """PostgreSQL-backed seen record storage using asyncpg."""

    def __init__(self):
        self.pool = None

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def mark_seen(self, scout_id: str, user_id: str, signature: str) -> bool:
        """Mark a signature as seen. Returns True if newly inserted, False if already existed.

        Uses INSERT ON CONFLICT DO NOTHING with RETURNING to detect whether the
        row was inserted (new) or skipped (duplicate).
        """
        await self._ensure_pool()

        result = await self.pool.fetchval(
            """
            INSERT INTO seen_records (scout_id, user_id, signature)
            VALUES ($1::uuid, $2::uuid, $3)
            ON CONFLICT (scout_id, signature) DO NOTHING
            RETURNING id
            """,
            scout_id, user_id, signature,
        )
        # If result is not None, the row was newly inserted
        return result is not None

    async def is_seen(self, scout_id: str, user_id: str, signature: str) -> bool:
        """Check if a signature has been seen for a scout."""
        await self._ensure_pool()

        result = await self.pool.fetchval(
            """
            SELECT TRUE FROM seen_records
            WHERE scout_id = $1::uuid AND user_id = $2::uuid AND signature = $3
            LIMIT 1
            """,
            scout_id, user_id, signature,
        )
        return result is not None

    async def delete_seen_records(self, user_id: str, scout_name: str) -> None:
        """Delete all seen records for a scout by name."""
        await self._ensure_pool()
        await self.pool.execute(
            """
            DELETE FROM seen_records
            WHERE user_id = $1::uuid
                AND scout_id = (SELECT id FROM scouts WHERE user_id = $1::uuid AND name = $2)
            """,
            user_id, scout_name,
        )
