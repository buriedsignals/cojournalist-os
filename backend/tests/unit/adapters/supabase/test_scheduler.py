"""Tests for SupabaseScheduler."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.supabase.scheduler import SupabaseScheduler


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_key = "test-service-key"
    return settings


@pytest.fixture
def scheduler(mock_pool, mock_settings):
    with patch("app.adapters.supabase.scheduler.get_settings", return_value=mock_settings):
        s = SupabaseScheduler()
        s.pool = mock_pool
    return s


class TestCreateSchedule:
    @pytest.mark.asyncio
    async def test_creates_cron_job(self, scheduler, mock_pool):
        mock_pool.execute = AsyncMock()

        target_config = {
            "scout_id": "abc-123",
            "user_id": "user-1",
            "scout_type": "pulse",
        }

        await scheduler.create_schedule(
            schedule_name="scout-user1-abc-myscout",
            cron="0 8 * * *",
            target_config=target_config,
        )

        mock_pool.execute.assert_called_once()
        call_args = mock_pool.execute.call_args
        sql = call_args[0][0]
        assert "cron.schedule" in sql
        assert call_args[0][1] == "scout-user1-abc-myscout"
        assert call_args[0][2] == "0 8 * * *"

    @pytest.mark.asyncio
    async def test_includes_edge_function_url(self, scheduler, mock_pool):
        mock_pool.execute = AsyncMock()

        await scheduler.create_schedule(
            schedule_name="test-schedule",
            cron="0 8 * * *",
            target_config={"scout_id": "abc"},
        )

        call_args = mock_pool.execute.call_args
        url_arg = call_args[0][3]
        assert "https://test.supabase.co/functions/v1/execute-scout" == url_arg


class TestDeleteSchedule:
    @pytest.mark.asyncio
    async def test_deletes_cron_job(self, scheduler, mock_pool):
        mock_pool.execute = AsyncMock()

        await scheduler.delete_schedule("scout-user1-abc-myscout")

        mock_pool.execute.assert_called_once()
        sql = mock_pool.execute.call_args[0][0]
        assert "cron.unschedule" in sql


class TestUpdateSchedule:
    @pytest.mark.asyncio
    async def test_updates_cron_expression(self, scheduler, mock_pool):
        mock_pool.execute = AsyncMock()

        await scheduler.update_schedule(
            schedule_name="test-schedule",
            cron="0 10 * * *",
            target_config={"scout_id": "abc"},
        )

        # Update is delete + create
        assert mock_pool.execute.call_count == 2
