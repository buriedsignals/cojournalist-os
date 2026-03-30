"""Tests for SupabasePostSnapshotStorage."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.adapters.supabase.post_snapshot_storage import SupabasePostSnapshotStorage


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def storage(mock_pool):
    s = SupabasePostSnapshotStorage()
    s.pool = mock_pool
    return s


class TestStoreSnapshot:
    @pytest.mark.asyncio
    async def test_upserts_snapshot(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="INSERT 1")

        await storage.store_snapshot(
            user_id="user-1",
            scout_id=str(uuid.uuid4()),
            platform="instagram",
            handle="test_user",
            posts=[{"post_id": "123", "text": "hello"}],
        )

        mock_pool.execute.assert_called_once()
        call_sql = mock_pool.execute.call_args[0][0]
        assert "INSERT INTO post_snapshots" in call_sql
        assert "ON CONFLICT" in call_sql


class TestGetSnapshot:
    @pytest.mark.asyncio
    async def test_returns_snapshot_when_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(),
            "scout_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "platform": "instagram",
            "handle": "test_user",
            "post_count": 2,
            "posts": [{"post_id": "1"}, {"post_id": "2"}],
            "updated_at": datetime.now(timezone.utc),
        })

        result = await storage.get_snapshot("user-1", str(uuid.uuid4()))
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_not_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await storage.get_snapshot("user-1", str(uuid.uuid4()))
        assert result == []
