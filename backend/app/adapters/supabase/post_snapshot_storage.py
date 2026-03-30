"""Supabase implementation of PostSnapshotStoragePort.

Uses asyncpg to execute SQL against the PostgreSQL post_snapshots table.
Stores social media post baselines for ID-based diffing.

DEPENDS ON: connection (get_pool), ports.storage (PostSnapshotStoragePort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import json
import logging

from app.adapters.supabase.connection import get_pool
from app.ports.storage import PostSnapshotStoragePort

logger = logging.getLogger(__name__)


class SupabasePostSnapshotStorage(PostSnapshotStoragePort):
    """PostgreSQL-backed post snapshot storage using asyncpg."""

    def __init__(self):
        self.pool = None

    async def _ensure_pool(self):
        if self.pool is None:
            self.pool = await get_pool()

    async def store_snapshot(self, user_id: str, scout_id: str,
                              platform: str, handle: str, posts: list[dict]) -> None:
        """Upsert a post snapshot for a scout. Uses ON CONFLICT on scout_id."""
        await self._ensure_pool()

        posts_json = json.dumps(posts)

        await self.pool.execute(
            """
            INSERT INTO post_snapshots (scout_id, user_id, platform, handle, post_count, posts)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
            ON CONFLICT (scout_id) DO UPDATE SET
                platform = EXCLUDED.platform,
                handle = EXCLUDED.handle,
                post_count = EXCLUDED.post_count,
                posts = EXCLUDED.posts,
                updated_at = NOW()
            """,
            scout_id, user_id, platform, handle, len(posts), posts_json,
        )

    async def get_snapshot(self, user_id: str, scout_id: str) -> list[dict]:
        """Get the stored post snapshot for a scout. Returns list of posts or []."""
        await self._ensure_pool()

        row = await self.pool.fetchrow(
            """
            SELECT posts FROM post_snapshots
            WHERE scout_id = $1::uuid AND user_id = $2::uuid
            """,
            scout_id, user_id,
        )

        if row is None:
            return []

        posts = row["posts"]
        if isinstance(posts, str):
            posts = json.loads(posts)
        return posts

    async def delete_snapshot(self, user_id: str, scout_name: str) -> None:
        """Delete the post snapshot for a scout by name."""
        await self._ensure_pool()
        await self.pool.execute(
            """
            DELETE FROM post_snapshots
            WHERE user_id = $1::uuid
                AND scout_id = (SELECT id FROM scouts WHERE user_id = $1::uuid AND name = $2)
            """,
            user_id, scout_name,
        )
