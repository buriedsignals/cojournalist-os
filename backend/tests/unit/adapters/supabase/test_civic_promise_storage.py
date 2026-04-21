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


class TestStorePromisesPydantic:
    """#48: store_promises should handle Pydantic objects, not just dicts."""

    @pytest.mark.asyncio
    async def test_handles_pydantic_objects(self, storage, mock_pool):
        from pydantic import BaseModel

        class MockPromise(BaseModel):
            promise_text: str
            context: str = None
            source_url: str = None
            source_title: str = None
            meeting_date: str = None

        mock_pool.executemany = AsyncMock()

        promises = [MockPromise(promise_text="Build new school by 2027")]
        await storage.store_promises("user-1", "scout-1", promises)

        mock_pool.executemany.assert_called_once()
        records = mock_pool.executemany.call_args[0][1]
        assert records[0][3] == "Build new school by 2027"  # promise_text at index 3

    @pytest.mark.asyncio
    async def test_converts_meeting_date_string_to_date(self, storage, mock_pool):
        """meeting_date strings should be converted to datetime.date objects."""
        mock_pool.executemany = AsyncMock()

        promises = [{
            "promise_text": "Fix roads by summer",
            "meeting_date": "2026-04-15",
        }]
        await storage.store_promises("user-1", "scout-1", promises)

        records = mock_pool.executemany.call_args[0][1]
        meeting_date = records[0][7]  # meeting_date at index 7
        assert isinstance(meeting_date, date)
        assert meeting_date == date(2026, 4, 15)

    @pytest.mark.asyncio
    async def test_handles_invalid_meeting_date_string(self, storage, mock_pool):
        """Invalid meeting_date strings should become None."""
        mock_pool.executemany = AsyncMock()

        promises = [{
            "promise_text": "Fix roads",
            "meeting_date": "not-a-date",
        }]
        await storage.store_promises("user-1", "scout-1", promises)

        records = mock_pool.executemany.call_args[0][1]
        assert records[0][7] is None  # Invalid date -> None


class TestDeletePromisesForScout:
    @pytest.mark.asyncio
    async def test_deletes_promises(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="DELETE 3")

        await storage.delete_promises_for_scout("user-1", "civic-scout-1")
        mock_pool.execute.assert_called_once()


class TestDueDateAndConfidencePersistence:
    """The extractor computes due_date and date_confidence; the adapter must
    actually insert them (previously they were silently dropped). Also verify
    the source_date → meeting_date mapping that was broken — the Pydantic
    Promise emits `source_date` but the adapter used to read `meeting_date`,
    so the meeting_date column was always NULL for civic promises."""

    @pytest.mark.asyncio
    async def test_source_date_maps_to_meeting_date_column(self, storage, mock_pool):
        mock_pool.executemany = AsyncMock()

        promises = [{
            "promise_text": "Expand bike lanes",
            "source_date": "2026-03-15",
            "due_date": "2027-12-31",
            "date_confidence": "high",
        }]
        await storage.store_promises("user-1", "scout-1", promises)

        records = mock_pool.executemany.call_args[0][1]
        # Positional tuple: (user_id, scraper, user_id, promise_text, context,
        #                    source_url, source_title, meeting_date, due_date,
        #                    date_confidence)
        assert records[0][7] == date(2026, 3, 15)  # meeting_date ← source_date

    @pytest.mark.asyncio
    async def test_due_date_and_confidence_are_inserted(self, storage, mock_pool):
        mock_pool.executemany = AsyncMock()

        promises = [{
            "promise_text": "Renovate town hall",
            "source_date": "2026-03-15",
            "due_date": "2028-06-30",
            "date_confidence": "medium",
        }]
        await storage.store_promises("user-1", "scout-1", promises)

        records = mock_pool.executemany.call_args[0][1]
        assert records[0][8] == date(2028, 6, 30)  # due_date
        assert records[0][9] == "medium"           # date_confidence

    @pytest.mark.asyncio
    async def test_invalid_date_confidence_becomes_null(self, storage, mock_pool):
        """Check constraint only allows high/medium/low — reject anything else."""
        mock_pool.executemany = AsyncMock()

        promises = [{
            "promise_text": "Install solar panels",
            "source_date": "2026-03-15",
            "due_date": "2030-12-31",
            "date_confidence": "very-very-sure",  # LLM misfire
        }]
        await storage.store_promises("user-1", "scout-1", promises)

        records = mock_pool.executemany.call_args[0][1]
        assert records[0][9] is None

    @pytest.mark.asyncio
    async def test_legacy_meeting_date_still_accepted(self, storage, mock_pool):
        """Dict callers passing the legacy 'meeting_date' key still work —
        source_date takes precedence, but meeting_date is the fallback."""
        mock_pool.executemany = AsyncMock()

        promises = [{
            "promise_text": "Legacy record",
            "meeting_date": "2026-01-10",
        }]
        await storage.store_promises("user-1", "scout-1", promises)

        records = mock_pool.executemany.call_args[0][1]
        assert records[0][7] == date(2026, 1, 10)
        assert records[0][8] is None  # no due_date
        assert records[0][9] is None  # no date_confidence
