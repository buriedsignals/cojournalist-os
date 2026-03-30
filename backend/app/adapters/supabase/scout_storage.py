"""Supabase implementation of ScoutStoragePort.

Uses asyncpg to execute SQL against the PostgreSQL scouts table.

DEPENDS ON: connection (get_pool), ports.storage (ScoutStoragePort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.adapters.supabase.connection import get_pool
from app.adapters.supabase.utils import row_to_dict
from app.ports.storage import ScoutStoragePort

logger = logging.getLogger(__name__)

# Columns to SELECT in scout queries (avoids SELECT *)
SCOUT_COLUMNS = """
    id, user_id, name, type, criteria, preferred_language,
    regularity, schedule_cron, schedule_timezone, topic,
    url, provider, source_mode, excluded_domains,
    platform, profile_handle, monitor_mode, track_removals,
    root_domain, tracked_urls, processed_pdf_urls,
    location, config, is_active, consecutive_failures,
    baseline_established_at, created_at, updated_at
"""

# Fields that map directly from input dict to SQL columns
SCOUT_INSERT_FIELDS = [
    "name", "type", "criteria", "preferred_language",
    "regularity", "schedule_cron", "schedule_timezone", "topic",
    "url", "provider", "source_mode", "excluded_domains",
    "platform", "profile_handle", "monitor_mode", "track_removals",
    "root_domain", "tracked_urls", "processed_pdf_urls",
    "location", "config",
]


class SupabaseScoutStorage(ScoutStoragePort):
    """PostgreSQL-backed scout storage using asyncpg."""

    def __init__(self):
        self.pool = None

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def create_scout(self, user_id: str, data: dict) -> dict:
        """Insert a new scout and return the created row."""
        await self._ensure_pool()

        # Build dynamic INSERT from provided fields
        columns = ["user_id"]
        placeholders = ["$1"]
        values = [user_id]
        idx = 2

        for field in SCOUT_INSERT_FIELDS:
            if field in data:
                columns.append(field)
                value = data[field]
                # JSONB fields need JSON serialization
                if field in ("location", "config") and isinstance(value, dict):
                    value = json.dumps(value)
                placeholders.append(f"${idx}")
                values.append(value)
                idx += 1

        sql = f"""
            INSERT INTO scouts ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            RETURNING {SCOUT_COLUMNS}
        """
        row = await self.pool.fetchrow(sql, *values)
        return row_to_dict(row)

    async def get_scout(self, user_id: str, scout_name: str) -> Optional[dict]:
        """Get a scout by user_id and name."""
        await self._ensure_pool()
        row = await self.pool.fetchrow(
            f"SELECT {SCOUT_COLUMNS} FROM scouts WHERE user_id = $1::uuid AND name = $2",
            user_id, scout_name,
        )
        return row_to_dict(row)

    async def get_scout_by_id(self, scout_id: str) -> Optional[dict]:
        """Get a scout by its UUID."""
        await self._ensure_pool()
        row = await self.pool.fetchrow(
            f"SELECT {SCOUT_COLUMNS} FROM scouts WHERE id = $1::uuid",
            scout_id,
        )
        return row_to_dict(row)

    async def list_scouts(self, user_id: str) -> list[dict]:
        """List all scouts for a user, ordered by creation time."""
        await self._ensure_pool()
        rows = await self.pool.fetch(
            f"SELECT {SCOUT_COLUMNS} FROM scouts WHERE user_id = $1::uuid ORDER BY created_at DESC",
            user_id,
        )
        return [row_to_dict(row) for row in rows]

    async def delete_scout(self, user_id: str, scout_name: str) -> None:
        """Delete a scout by user_id and name. CASCADE deletes related records."""
        await self._ensure_pool()
        await self.pool.execute(
            "DELETE FROM scouts WHERE user_id = $1::uuid AND name = $2",
            user_id, scout_name,
        )

    async def update_scout(self, user_id: str, scout_name: str, updates: dict) -> Optional[dict]:
        """Update scout fields and return the updated row."""
        await self._ensure_pool()

        if not updates:
            return await self.get_scout(user_id, scout_name)

        set_clauses = []
        values = []
        idx = 1

        for field, value in updates.items():
            if field in ("location", "config") and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{field} = ${idx}")
            values.append(value)
            idx += 1

        values.append(user_id)
        values.append(scout_name)

        sql = f"""
            UPDATE scouts
            SET {', '.join(set_clauses)}
            WHERE user_id = ${idx}::uuid AND name = ${idx + 1}
            RETURNING {SCOUT_COLUMNS}
        """
        row = await self.pool.fetchrow(sql, *values)
        return row_to_dict(row)

    async def deactivate_scout(self, scout_id: str) -> None:
        """Set is_active = FALSE for a scout by ID."""
        await self._ensure_pool()
        await self.pool.execute(
            "UPDATE scouts SET is_active = FALSE WHERE id = $1::uuid",
            scout_id,
        )
