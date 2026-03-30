"""Tests for SupabaseRunStorage."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.supabase.run_storage import SupabaseRunStorage


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def storage(mock_pool):
    s = SupabaseRunStorage()
    s.pool = mock_pool
    return s


class TestStoreRun:
    @pytest.mark.asyncio
    async def test_stores_run_and_returns_dict(self, storage, mock_pool):
        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": run_id,
            "scout_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "status": "success",
            "scraper_status": True,
            "criteria_status": True,
            "notification_sent": True,
            "articles_count": 5,
            "error_message": None,
            "started_at": now,
            "completed_at": now,
            "expires_at": now,
        })

        result = await storage.store_run(
            scout_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            status="success",
            articles_count=5,
            scraper_status=True,
            criteria_status=True,
            notification_sent=True,
        )

        assert result["status"] == "success"
        assert result["articles_count"] == 5
        mock_pool.fetchrow.assert_called_once()


class TestGetLatestRuns:
    @pytest.mark.asyncio
    async def test_returns_latest_runs(self, storage, mock_pool):
        mock_pool.fetch = AsyncMock(return_value=[
            {"id": uuid.uuid4(), "status": "success", "started_at": datetime.now(timezone.utc)},
            {"id": uuid.uuid4(), "status": "error", "started_at": datetime.now(timezone.utc)},
        ])

        result = await storage.get_latest_runs("user-1", limit=10)
        assert len(result) == 2


class TestGetLatestRunForScout:
    @pytest.mark.asyncio
    async def test_returns_latest_run(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(),
            "status": "success",
        })

        result = await storage.get_latest_run_for_scout(str(uuid.uuid4()))
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_runs(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await storage.get_latest_run_for_scout(str(uuid.uuid4()))
        assert result is None
