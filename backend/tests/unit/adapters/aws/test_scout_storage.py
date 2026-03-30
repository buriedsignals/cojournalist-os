"""Unit tests for DynamoDBScoutStorage adapter."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from app.adapters.aws.scout_storage import DynamoDBScoutStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.scout_storage.get_table", return_value=mock_table):
        return DynamoDBScoutStorage()


# ---------------------------------------------------------------------------
# create_scout_sync
# ---------------------------------------------------------------------------

class TestCreateScoutSync:
    def test_puts_scraper_record_for_web_scout(self, adapter, mock_table):
        data = {
            "scout_type": "web",
            "scraper_name": "my-scout",
            "url": "https://example.com",
            "criteria": "price drop",
            "regularity": "daily",
            "time": "08:00",
            "monitoring": "EMAIL",
            "preferred_language": "en",
            "cron_expression": "0 8 * * *",
            "timezone": "UTC",
        }
        adapter.create_scout_sync("user123", data)

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user123"
        assert item["SK"] == "SCRAPER#my-scout"
        assert item["scout_type"] == "web"
        assert item["url"] == "https://example.com"
        assert item["criteria"] == "price drop"

    def test_puts_scraper_record_for_pulse_scout(self, adapter, mock_table):
        data = {
            "scout_type": "pulse",
            "scraper_name": "pulse-scout",
            "location": {"city": "Oslo", "country": "Norway"},
            "regularity": "daily",
            "time": "07:00",
            "monitoring": "EMAIL",
            "preferred_language": "no",
            "cron_expression": "0 7 * * *",
            "timezone": "Europe/Oslo",
        }
        adapter.create_scout_sync("user456", data)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user456"
        assert item["SK"] == "SCRAPER#pulse-scout"
        assert item["scout_type"] == "pulse"
        assert item["location"] == {"city": "Oslo", "country": "Norway"}

    def test_puts_scraper_record_for_social_scout(self, adapter, mock_table):
        data = {
            "scout_type": "social",
            "scraper_name": "social-scout",
            "platform": "instagram",
            "profile_handle": "testhandle",
            "monitor_mode": "summarize",
            "track_removals": False,
            "regularity": "daily",
            "time": "09:00",
            "monitoring": "EMAIL",
            "preferred_language": "en",
            "cron_expression": "0 9 * * *",
            "timezone": "UTC",
        }
        adapter.create_scout_sync("user789", data)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == "SCRAPER#social-scout"
        assert item["platform"] == "instagram"
        assert item["profile_handle"] == "testhandle"
        assert item["monitor_mode"] == "summarize"

    def test_puts_scraper_record_for_civic_scout(self, adapter, mock_table):
        data = {
            "scout_type": "civic",
            "scraper_name": "civic-scout",
            "root_domain": "council.example.gov",
            "tracked_urls": ["https://council.example.gov/meetings"],
            "criteria": "housing",
            "content_hash": "abc123",
            "processed_pdf_urls": [],
            "regularity": "weekly",
            "time": "10:00",
            "monitoring": "EMAIL",
            "preferred_language": "en",
            "cron_expression": "0 10 * * 1",
            "timezone": "UTC",
        }
        adapter.create_scout_sync("user_civic", data)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == "SCRAPER#civic-scout"
        assert item["root_domain"] == "council.example.gov"
        assert item["tracked_urls"] == ["https://council.example.gov/meetings"]

    def test_converts_floats_to_decimal(self, adapter, mock_table):
        data = {
            "scout_type": "web",
            "scraper_name": "my-scout",
            "url": "https://example.com",
            "criteria": "test",
            "regularity": "daily",
            "time": "08:00",
            "monitoring": "EMAIL",
            "preferred_language": "en",
            "cron_expression": "0 8 * * *",
            "timezone": "UTC",
            "location": {"lat": 59.9139, "lon": 10.7522},
        }
        adapter.create_scout_sync("user123", data)

        item = mock_table.put_item.call_args[1]["Item"]
        # location dict with float coordinates gets converted to Decimal
        location = item.get("location", {})
        for v in location.values():
            assert isinstance(v, Decimal)

    def test_returns_scraper_name(self, adapter, mock_table):
        data = {
            "scout_type": "web",
            "scraper_name": "my-scout",
            "url": "https://example.com",
            "criteria": "test",
            "regularity": "daily",
            "time": "08:00",
            "monitoring": "EMAIL",
            "preferred_language": "en",
            "cron_expression": "0 8 * * *",
            "timezone": "UTC",
        }
        result = adapter.create_scout_sync("user123", data)
        assert result["scraper_name"] == "my-scout"


# ---------------------------------------------------------------------------
# get_scout_sync
# ---------------------------------------------------------------------------

class TestGetScoutSync:
    def _make_scraper_item(self):
        return {
            "PK": "user1",
            "SK": "SCRAPER#test-scout",
            "scout_type": "web",
            "url": "https://example.com",
            "created_at": "2024-01-01T00:00:00Z",
        }

    def test_returns_none_when_not_found(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": None}
        # get_item returning no Item key
        mock_table.get_item.return_value = {}
        result = adapter.get_scout_sync("user1", "missing-scout")
        assert result is None

    def test_returns_scout_with_name(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": self._make_scraper_item()}
        # _query_by_prefix_sync calls table.query — return empty pages
        mock_table.query.return_value = {"Items": [], "Count": 0}

        result = adapter.get_scout_sync("user1", "test-scout")
        assert result is not None
        assert result["name"] == "test-scout"
        assert result["scout_type"] == "web"

    def test_merges_latest_time_record(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": self._make_scraper_item()}

        time_items = [
            {
                "PK": "user1",
                "SK": "TIME#2024-01-02T10:00:00Z#test-scout",
                "scraper_name": "test-scout",
                "run_time": "2024-01-02T10:00:00Z",
                "scraper_status": True,
                "criteria_status": True,
                "notification_sent": True,
            }
        ]

        # get_scout_sync calls _query_by_prefix_sync twice:
        #   call 0 → TIME# records
        #   call 1 → EXEC#{name}# records
        mock_table.query.side_effect = [
            {"Items": time_items},  # TIME# query
            {"Items": []},          # EXEC# query
        ]

        result = adapter.get_scout_sync("user1", "test-scout")
        assert result["last_run"] == "2024-01-02T10:00:00Z"
        assert result["scraper_status"] is True
        assert result["notification_sent"] is True

    def test_merges_exec_summary(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": self._make_scraper_item()}

        exec_items = [
            {
                "PK": "user1",
                "SK": "EXEC#test-scout#1234567890#exec1",
                "summary_text": "Found price change",
            }
        ]

        # get_scout_sync calls _query_by_prefix_sync twice:
        #   call 0 → TIME# records (no match for this scout)
        #   call 1 → EXEC#{name}# records
        mock_table.query.side_effect = [
            {"Items": []},          # TIME# query — no run yet
            {"Items": exec_items},  # EXEC# query
        ]

        result = adapter.get_scout_sync("user1", "test-scout")
        assert result["card_summary"] == "Found price change"

    def test_converts_decimals(self, adapter, mock_table):
        item = self._make_scraper_item()
        item["some_count"] = Decimal("42")
        mock_table.get_item.return_value = {"Item": item}
        mock_table.query.return_value = {"Items": []}

        result = adapter.get_scout_sync("user1", "test-scout")
        assert result["some_count"] == 42
        assert isinstance(result["some_count"], int)


# ---------------------------------------------------------------------------
# get_scout_by_id_sync
# ---------------------------------------------------------------------------

class TestGetScoutByIdSync:
    def test_raises_not_implemented(self, adapter):
        with pytest.raises(NotImplementedError):
            adapter.get_scout_by_id_sync("some-id")


# ---------------------------------------------------------------------------
# list_scouts_sync
# ---------------------------------------------------------------------------

class TestListScoutsSync:
    def test_returns_empty_list_when_no_scouts(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.list_scouts_sync("user1")
        assert result == []

    def test_returns_scouts_with_merged_data(self, adapter, mock_table):
        scraper_items = [
            {
                "PK": "user1",
                "SK": "SCRAPER#scout-a",
                "scout_type": "web",
                "created_at": "2024-01-02T00:00:00Z",
            }
        ]
        time_items = [
            {
                "PK": "user1",
                "SK": "TIME#2024-01-02T10:00:00Z#scout-a",
                "scraper_name": "scout-a",
                "run_time": "2024-01-02T10:00:00Z",
                "scraper_status": True,
                "criteria_status": False,
                "notification_sent": False,
            }
        ]
        exec_items = [
            {
                "PK": "user1",
                "SK": "EXEC#scout-a#1234567890#exec1",
                "summary_text": "Summary A",
            }
        ]

        # list_scouts_sync calls _query_by_prefix_sync three times:
        #   call 0 → SCRAPER# records
        #   call 1 → TIME# records
        #   call 2 → EXEC# records
        mock_table.query.side_effect = [
            {"Items": scraper_items},
            {"Items": time_items},
            {"Items": exec_items},
        ]

        result = adapter.list_scouts_sync("user1")
        assert len(result) == 1
        scout = result[0]
        assert scout["name"] == "scout-a"
        assert scout["last_run"] == "2024-01-02T10:00:00Z"
        assert scout["card_summary"] == "Summary A"

    def test_sorts_by_created_at_descending(self, adapter, mock_table):
        scraper_items = [
            {
                "PK": "user1",
                "SK": "SCRAPER#older-scout",
                "scout_type": "web",
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "PK": "user1",
                "SK": "SCRAPER#newer-scout",
                "scout_type": "web",
                "created_at": "2024-01-03T00:00:00Z",
            },
        ]

        # list_scouts_sync: SCRAPER# → TIME# → EXEC#
        mock_table.query.side_effect = [
            {"Items": scraper_items},
            {"Items": []},   # TIME#
            {"Items": []},   # EXEC#
        ]

        result = adapter.list_scouts_sync("user1")
        assert result[0]["name"] == "newer-scout"
        assert result[1]["name"] == "older-scout"

    def test_latest_run_per_scout(self, adapter, mock_table):
        """Only first TIME# record per scout name is used (list is sorted desc)."""
        scraper_items = [
            {
                "PK": "user1",
                "SK": "SCRAPER#scout-a",
                "scout_type": "web",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]
        time_items = [
            {
                "PK": "user1",
                "SK": "TIME#2024-01-03T10:00:00Z#scout-a",
                "scraper_name": "scout-a",
                "run_time": "2024-01-03T10:00:00Z",
                "scraper_status": True,
            },
            {
                "PK": "user1",
                "SK": "TIME#2024-01-02T10:00:00Z#scout-a",
                "scraper_name": "scout-a",
                "run_time": "2024-01-02T10:00:00Z",
                "scraper_status": False,
            },
        ]

        # list_scouts_sync: SCRAPER# → TIME# → EXEC#
        mock_table.query.side_effect = [
            {"Items": scraper_items},
            {"Items": time_items},
            {"Items": []},  # EXEC#
        ]

        result = adapter.list_scouts_sync("user1")
        # First TIME# record (index 0, most recent because ScanIndexForward=False)
        assert result[0]["last_run"] == "2024-01-03T10:00:00Z"


# ---------------------------------------------------------------------------
# delete_scout_sync
# ---------------------------------------------------------------------------

class TestDeleteScoutSync:
    def test_deletes_scraper_record(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}

        adapter.delete_scout_sync("user1", "my-scout")

        mock_table.delete_item.assert_any_call(
            Key={"PK": "user1", "SK": "SCRAPER#my-scout"}
        )

    def test_returns_scraper_name(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}

        result = adapter.delete_scout_sync("user1", "my-scout")
        assert result["scraper_name"] == "my-scout"

    def test_result_contains_records_deleted(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}

        result = adapter.delete_scout_sync("user1", "my-scout")
        assert "records_deleted" in result


# ---------------------------------------------------------------------------
# update_scout_sync
# ---------------------------------------------------------------------------

class TestUpdateScoutSync:
    def test_calls_update_item_with_correct_key(self, adapter, mock_table):
        mock_table.update_item.return_value = {
            "Attributes": {
                "PK": "user1",
                "SK": "SCRAPER#my-scout",
                "criteria": "new criteria",
            }
        }
        result = adapter.update_scout_sync("user1", "my-scout", {"criteria": "new criteria"})

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"PK": "user1", "SK": "SCRAPER#my-scout"}

    def test_builds_update_expression_from_updates(self, adapter, mock_table):
        mock_table.update_item.return_value = {"Attributes": {}}
        adapter.update_scout_sync("user1", "my-scout", {"criteria": "test", "url": "https://new.com"})

        call_kwargs = mock_table.update_item.call_args[1]
        expr = call_kwargs.get("UpdateExpression", "")
        assert "SET" in expr

    def test_returns_updated_item(self, adapter, mock_table):
        updated = {
            "PK": "user1",
            "SK": "SCRAPER#my-scout",
            "criteria": "updated",
        }
        mock_table.update_item.return_value = {"Attributes": updated}
        result = adapter.update_scout_sync("user1", "my-scout", {"criteria": "updated"})
        assert result["criteria"] == "updated"

    def test_returns_none_when_no_attributes(self, adapter, mock_table):
        mock_table.update_item.return_value = {}
        result = adapter.update_scout_sync("user1", "my-scout", {"criteria": "x"})
        assert result is None


# ---------------------------------------------------------------------------
# deactivate_scout_sync
# ---------------------------------------------------------------------------

class TestDeactivateScoutSync:
    def test_raises_not_implemented(self, adapter):
        with pytest.raises(NotImplementedError):
            adapter.deactivate_scout_sync("some-id")


# ---------------------------------------------------------------------------
# _query_by_prefix_sync — pagination
# ---------------------------------------------------------------------------

class TestQueryByPrefixSync:
    def test_handles_pagination(self, adapter, mock_table):
        page1 = {
            "Items": [{"PK": "u1", "SK": "SCRAPER#a"}],
            "LastEvaluatedKey": {"PK": "u1", "SK": "SCRAPER#a"},
        }
        page2 = {"Items": [{"PK": "u1", "SK": "SCRAPER#b"}]}

        mock_table.query.side_effect = [page1, page2]

        items = adapter._query_by_prefix_sync("u1", "SCRAPER#")
        assert len(items) == 2
        assert items[0]["SK"] == "SCRAPER#a"
        assert items[1]["SK"] == "SCRAPER#b"
        # Second call should include ExclusiveStartKey
        second_call_kwargs = mock_table.query.call_args_list[1][1]
        assert "ExclusiveStartKey" in second_call_kwargs

    def test_passes_scan_forward_flag(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter._query_by_prefix_sync("u1", "TIME#", scan_forward=False)
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_passes_projection(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter._query_by_prefix_sync("u1", "SCRAPER#", projection="PK, SK")
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ProjectionExpression"] == "PK, SK"


# ---------------------------------------------------------------------------
# _batch_delete_sync — chunking
# ---------------------------------------------------------------------------

class TestBatchDeleteSync:
    def test_does_nothing_for_empty_list(self, adapter, mock_table):
        adapter._batch_delete_sync([])
        mock_table.batch_writer.assert_not_called()

    def test_chunks_into_25_items(self, adapter, mock_table):
        items = [{"PK": "u1", "SK": f"TIME#ts#{i}"} for i in range(30)]

        batch_writer_mock = MagicMock()
        batch_writer_mock.__enter__ = MagicMock(return_value=batch_writer_mock)
        batch_writer_mock.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer_mock

        adapter._batch_delete_sync(items)

        # Should have called batch_writer twice (25 + 5)
        assert mock_table.batch_writer.call_count == 2
        # Total delete_item calls across both batches: 30
        assert batch_writer_mock.delete_item.call_count == 30

    def test_deletes_with_correct_keys(self, adapter, mock_table):
        items = [{"PK": "u1", "SK": "TIME#ts#scout"}]

        batch_writer_mock = MagicMock()
        batch_writer_mock.__enter__ = MagicMock(return_value=batch_writer_mock)
        batch_writer_mock.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer_mock

        adapter._batch_delete_sync(items)
        batch_writer_mock.delete_item.assert_called_once_with(
            Key={"PK": "u1", "SK": "TIME#ts#scout"}
        )


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_create_scout_async(self, adapter, mock_table):
        data = {
            "scout_type": "web",
            "scraper_name": "async-scout",
            "url": "https://example.com",
            "criteria": "test",
            "regularity": "daily",
            "time": "08:00",
            "monitoring": "EMAIL",
            "preferred_language": "en",
            "cron_expression": "0 8 * * *",
            "timezone": "UTC",
        }
        result = await adapter.create_scout("user1", data)
        mock_table.put_item.assert_called_once()
        assert result["scraper_name"] == "async-scout"

    @pytest.mark.asyncio
    async def test_list_scouts_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.list_scouts("user1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_scout_async_returns_none_when_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_scout("user1", "missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_scout_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.delete_scout("user1", "my-scout")
        assert result["scraper_name"] == "my-scout"

    @pytest.mark.asyncio
    async def test_get_scout_by_id_raises(self, adapter):
        with pytest.raises(NotImplementedError):
            await adapter.get_scout_by_id("some-id")

    @pytest.mark.asyncio
    async def test_deactivate_scout_raises(self, adapter):
        with pytest.raises(NotImplementedError):
            await adapter.deactivate_scout("some-id")
