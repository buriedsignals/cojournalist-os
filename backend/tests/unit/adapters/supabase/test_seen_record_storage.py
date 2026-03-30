"""Tests for SupabaseSeenRecordStorage."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.adapters.supabase.seen_record_storage import SupabaseSeenRecordStorage


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def storage(mock_pool):
    s = SupabaseSeenRecordStorage()
    s.pool = mock_pool
    return s


class TestMarkSeen:
    @pytest.mark.asyncio
    async def test_returns_true_on_new_record(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=uuid.uuid4())

        result = await storage.mark_seen(str(uuid.uuid4()), "user-1", "sig-abc123")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_existing_record(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=None)

        result = await storage.mark_seen(str(uuid.uuid4()), "user-1", "sig-abc123")
        assert result is False


class TestIsSeen:
    @pytest.mark.asyncio
    async def test_returns_true_when_seen(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=True)

        result = await storage.is_seen(str(uuid.uuid4()), "user-1", "sig-abc123")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_seen(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=None)

        result = await storage.is_seen(str(uuid.uuid4()), "user-1", "sig-abc123")
        assert result is False
