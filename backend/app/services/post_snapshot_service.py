"""
PostSnapshotService — POSTS# record management for social scouts.

Delegates all storage operations to the PostSnapshotStoragePort adapter,
selected at runtime based on DEPLOYMENT_TARGET (AWS DynamoDB or Supabase PostgreSQL).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PostSnapshotService:
    """CRUD for social scout post snapshots, delegating to storage adapter."""

    def __init__(self, snapshot_storage=None) -> None:
        if snapshot_storage is None:
            from app.dependencies.providers import get_post_snapshot_storage
            snapshot_storage = get_post_snapshot_storage()
        self.storage = snapshot_storage

    async def get_snapshot(self, user_id: str, scout_name: str) -> Optional[dict]:
        """Fetch snapshot for a scout. Returns dict or None."""
        try:
            return await self.storage.get_snapshot(user_id, scout_name)
        except Exception as e:
            logger.warning(f"Failed to load snapshot for {scout_name}: {e}")
            return None

    async def store_snapshot(
        self,
        user_id: str,
        scout_name: str,
        posts: list[dict],
        platform: str,
        handle: str,
    ) -> None:
        """Persist a post snapshot for a scout."""
        await self.storage.store_snapshot(user_id, scout_name, platform, handle, posts)

    async def delete_snapshot(self, user_id: str, scout_name: str) -> None:
        """Delete a snapshot record."""
        try:
            await self.storage.delete_snapshot(user_id, scout_name)
        except Exception as e:
            logger.warning(f"Failed to delete snapshot for {scout_name}: {e}")
