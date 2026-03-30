"""Tests for SupabaseCivicPromiseStorage."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.adapters.supabase.civic_promise_storage import SupabaseCivicPromiseStorage


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def storage(mock_pool):
    s = SupabaseCivicPromiseStorage()
    s.pool = mock_pool
    return s


class TestStorePromises:
    @pytest.mark.asyncio
    async def test_stores_multiple_promises(self, storage, mock_pool):
        mock_pool.executemany = AsyncMock()

        promises = [
            {
                "promise_text": "Build new community center",
                "context": "Council meeting discussion",
                "source_url": "https://council.example.com/minutes",
                "source_title": "March Meeting Minutes",
                "meeting_date": date(2026, 3, 15),
            },
            {
                "promise_text": "Fix road potholes by summer",
                "context": "Public works session",
                "source_url": "https://council.example.com/minutes2",
                "source_title": "Public Works Report",
                "meeting_date": date(2026, 3, 20),
            },
        ]

        await storage.store_promises(
            user_id="user-1",
            scraper_name="civic-scout-1",
            promises=promises,
        )
        mock_pool.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_empty_list_without_error(self, storage, mock_pool):
        await storage.store_promises("user-1", "civic-scout-1", [])
        mock_pool.executemany.assert_not_called()


class TestGetStoredHash:
    @pytest.mark.asyncio
    async def test_returns_hash_when_exists(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value="abc123hash")

        result = await storage.get_stored_hash("user-1", "civic-scout-1")
        assert result == "abc123hash"

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_record(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=None)

        result = await storage.get_stored_hash("user-1", "civic-scout-1")
        assert result == ""


class TestGetProcessedUrls:
    @pytest.mark.asyncio
    async def test_returns_url_list(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=[
            "https://council.example.com/meeting1",
            "https://council.example.com/meeting2",
        ])

        result = await storage.get_processed_urls("user-1", "civic-scout-1")
        assert result == [
            "https://council.example.com/meeting1",
            "https://council.example.com/meeting2",
        ]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self, storage, mock_pool):
        mock_pool.fetchval = AsyncMock(return_value=None)

        result = await storage.get_processed_urls("user-1", "civic-scout-1")
        assert result == []


class TestUpdateScraperRecord:
    @pytest.mark.asyncio
    async def test_updates_scraper_record(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="UPDATE 1")

        await storage.update_scraper_record(
            "user-1", "civic-scout-1",
            content_hash="newhash123",
            new_processed=["https://council.example.com/meeting1"],
        )
        mock_pool.execute.assert_called_once()


class TestMarkPromisesNotified:
    @pytest.mark.asyncio
    async def test_marks_promises_as_notified(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="UPDATE 2")

        promise_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        await storage.mark_promises_notified("user-1", "civic-scout-1", promise_ids)
        mock_pool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_list_is_noop(self, storage, mock_pool):
        await storage.mark_promises_notified("user-1", "civic-scout-1", [])
        mock_pool.execute.assert_not_called()


class TestDeletePromisesForScout:
    @pytest.mark.asyncio
    async def test_deletes_promises(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="DELETE 3")

        await storage.delete_promises_for_scout("user-1", "civic-scout-1")
        mock_pool.execute.assert_called_once()
