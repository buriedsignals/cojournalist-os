"""Tests for SupabaseScoutStorage."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.supabase.scout_storage import SupabaseScoutStorage


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    return pool


@pytest.fixture
def storage(mock_pool):
    with patch("app.adapters.supabase.scout_storage.get_pool", return_value=mock_pool):
        s = SupabaseScoutStorage()
        s.pool = mock_pool
    return s


class TestCreateScout:
    @pytest.mark.asyncio
    async def test_creates_scout_and_returns_dict(self, storage, mock_pool):
        scout_id = uuid.uuid4()
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": scout_id,
            "user_id": uuid.uuid4(),
            "name": "my-scout",
            "type": "pulse",
            "criteria": "local news",
            "preferred_language": "en",
            "regularity": "daily",
            "schedule_cron": "0 8 * * *",
            "schedule_timezone": "UTC",
            "topic": None,
            "url": None,
            "provider": None,
            "source_mode": "reliable",
            "excluded_domains": None,
            "platform": None,
            "profile_handle": None,
            "monitor_mode": None,
            "track_removals": False,
            "root_domain": None,
            "tracked_urls": None,
            "processed_pdf_urls": None,
            "location": None,
            "config": {},
            "is_active": True,
            "consecutive_failures": 0,
            "baseline_established_at": None,
            "created_at": "2026-03-29T10:00:00+00:00",
            "updated_at": "2026-03-29T10:00:00+00:00",
        })

        result = await storage.create_scout("user-1", {
            "name": "my-scout",
            "type": "pulse",
            "criteria": "local news",
            "regularity": "daily",
            "schedule_cron": "0 8 * * *",
            "source_mode": "reliable",
        })

        assert result["name"] == "my-scout"
        assert result["type"] == "pulse"
        mock_pool.fetchrow.assert_called_once()


class TestGetScout:
    @pytest.mark.asyncio
    async def test_returns_scout_when_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(),
            "name": "test-scout",
            "type": "web",
            "is_active": True,
        })

        result = await storage.get_scout("user-1", "test-scout")
        assert result["name"] == "test-scout"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await storage.get_scout("user-1", "nonexistent")
        assert result is None


class TestListScouts:
    @pytest.mark.asyncio
    async def test_returns_all_user_scouts(self, storage, mock_pool):
        mock_pool.fetch = AsyncMock(return_value=[
            {"id": uuid.uuid4(), "name": "scout-1", "type": "pulse"},
            {"id": uuid.uuid4(), "name": "scout-2", "type": "web"},
        ])

        result = await storage.list_scouts("user-1")
        assert len(result) == 2


class TestDeleteScout:
    @pytest.mark.asyncio
    async def test_deletes_scout(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="DELETE 1")

        await storage.delete_scout("user-1", "my-scout")
        mock_pool.execute.assert_called_once()


class TestUpdateScout:
    @pytest.mark.asyncio
    async def test_updates_and_returns_scout(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(),
            "name": "my-scout",
            "type": "pulse",
            "criteria": "updated criteria",
        })

        result = await storage.update_scout("user-1", "my-scout", {"criteria": "updated criteria"})
        assert result["criteria"] == "updated criteria"


class TestDeactivateScout:
    @pytest.mark.asyncio
    async def test_deactivates_scout(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="UPDATE 1")

        await storage.deactivate_scout(str(uuid.uuid4()))
        mock_pool.execute.assert_called_once()


class TestGetScoutById:
    @pytest.mark.asyncio
    async def test_returns_scout_by_id(self, storage, mock_pool):
        scout_id = str(uuid.uuid4())
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": scout_id,
            "name": "my-scout",
            "type": "web",
        })

        result = await storage.get_scout_by_id(scout_id)
        assert result["name"] == "my-scout"
