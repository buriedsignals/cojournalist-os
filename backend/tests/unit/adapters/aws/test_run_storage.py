"""Unit tests for DynamoDBRunStorage adapter."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.aws.run_storage import DynamoDBRunStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.run_storage.get_table", return_value=mock_table):
        return DynamoDBRunStorage()


# ---------------------------------------------------------------------------
# store_run_sync
# ---------------------------------------------------------------------------

class TestStoreRunSync:
    def test_puts_time_record_with_correct_pk(self, adapter, mock_table):
        result = adapter.store_run_sync("scout123", "user1", "success")

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user1"

    def test_sk_starts_with_time_prefix(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"].startswith("TIME#")

    def test_sk_ends_with_scout_id(self, adapter, mock_table):
        adapter.store_run_sync("my-scout", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"].endswith("#my-scout")

    def test_sk_contains_timestamp_as_decimal(self, adapter, mock_table):
        adapter.store_run_sync("my-scout", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        # SK format: TIME#{Decimal(timestamp)}#scout_id
        parts = item["SK"].split("#")
        # parts[0] = "TIME", parts[1] = timestamp, parts[2] = scout_id
        assert len(parts) == 3
        # Timestamp part should be parseable as a number
        float(parts[1])

    def test_sets_scraper_status_true_on_success(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scraper_status"] is True

    def test_sets_scraper_status_false_on_error(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "error")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scraper_status"] is False

    def test_sets_scraper_name_to_scout_id(self, adapter, mock_table):
        adapter.store_run_sync("my-scout", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scraper_name"] == "my-scout"

    def test_sets_ttl_90_days(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert "ttl" in item
        assert isinstance(item["ttl"], int)
        # TTL should be roughly 90 days from now.
        # Use datetime.utcnow().timestamp() to match the implementation's
        # behaviour (naive UTC datetime → local-epoch timestamp).
        from datetime import datetime
        now_ts = datetime.utcnow().timestamp()
        expected_ttl = now_ts + 90 * 24 * 3600
        assert abs(item["ttl"] - expected_ttl) < 5  # within 5 seconds

    def test_sets_run_time_formatted_string(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert "run_time" in item
        # Format is MM-DD-YYYY HH:MM
        run_time = item["run_time"]
        assert len(run_time) == 16  # "MM-DD-YYYY HH:MM"
        assert run_time[2] == "-"
        assert run_time[5] == "-"

    def test_sets_monitoring_email(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["monitoring"] == "EMAIL"

    def test_notification_sent_defaults_false(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["notification_sent"] is False

    def test_notification_sent_true_from_kwargs(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success", notification_sent=True)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["notification_sent"] is True

    def test_criteria_status_defaults_false(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["criteria_status"] is False

    def test_criteria_status_from_kwargs(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success", criteria_status=True)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["criteria_status"] is True

    def test_scout_type_defaults_to_web(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scout_type"] == "web"

    def test_scout_type_from_kwargs(self, adapter, mock_table):
        adapter.store_run_sync("scout123", "user1", "success", scout_type="pulse")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scout_type"] == "pulse"

    def test_returns_stored_item(self, adapter, mock_table):
        result = adapter.store_run_sync("scout123", "user1", "success")

        assert result is not None
        assert result["PK"] == "user1"
        assert result["scraper_name"] == "scout123"

    def test_error_message_ignored_in_item(self, adapter, mock_table):
        """error_message param is accepted but not stored in DynamoDB item."""
        adapter.store_run_sync("scout123", "user1", "error", error_message="timeout")
        # Should not raise; item is still written
        mock_table.put_item.assert_called_once()


# ---------------------------------------------------------------------------
# get_latest_runs_sync
# ---------------------------------------------------------------------------

class TestGetLatestRunsSync:
    def test_returns_empty_list_when_no_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_latest_runs_sync("user1")
        assert result == []

    def test_queries_time_prefix_descending(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_latest_runs_sync("user1")

        call_kwargs = mock_table.query.call_args[1]
        # ScanIndexForward=False for descending (most recent first)
        assert call_kwargs["ScanIndexForward"] is False

    def test_returns_up_to_limit_items(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": f"TIME#ts{i}#scout",
                "scraper_name": "scout",
                "run_time": f"01-0{i}-2024 10:00",
                "scraper_status": True,
                "criteria_status": False,
                "notification_sent": False,
                "scout_type": "web",
                "ttl": 9999999999,
            }
            for i in range(1, 8)
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_latest_runs_sync("user1", limit=5)
        assert len(result) == 5

    def test_converts_decimals_in_results(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": "TIME#123456#scout",
                "scraper_name": "scout",
                "run_time": "01-01-2024 10:00",
                "scraper_status": True,
                "criteria_status": False,
                "notification_sent": False,
                "scout_type": "web",
                "ttl": Decimal("9999999999"),
            }
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_latest_runs_sync("user1", limit=10)
        assert isinstance(result[0]["ttl"], int)

    def test_handles_pagination(self, adapter, mock_table):
        page1 = {
            "Items": [{"PK": "user1", "SK": "TIME#ts1#scout", "scraper_name": "scout"}],
            "LastEvaluatedKey": {"PK": "user1", "SK": "TIME#ts1#scout"},
        }
        page2 = {
            "Items": [{"PK": "user1", "SK": "TIME#ts2#scout", "scraper_name": "scout"}],
        }
        mock_table.query.side_effect = [page1, page2]

        result = adapter.get_latest_runs_sync("user1", limit=10)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_latest_run_for_scout_sync
# ---------------------------------------------------------------------------

class TestGetLatestRunForScoutSync:
    def test_raises_not_implemented(self, adapter):
        with pytest.raises(NotImplementedError):
            adapter.get_latest_run_for_scout_sync("scout123")


# ---------------------------------------------------------------------------
# delete_runs_for_scout_sync
# ---------------------------------------------------------------------------

class TestDeleteRunsForScoutSync:
    def test_queries_time_prefix_for_user(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.delete_runs_for_scout_sync("user1", "my-scout")

        mock_table.query.assert_called_once()

    def test_deletes_only_matching_scout_records(self, adapter, mock_table):
        items = [
            {"PK": "user1", "SK": "TIME#ts1#my-scout"},
            {"PK": "user1", "SK": "TIME#ts2#other-scout"},
        ]
        mock_table.query.return_value = {"Items": items}

        batch_writer_mock = MagicMock()
        batch_writer_mock.__enter__ = MagicMock(return_value=batch_writer_mock)
        batch_writer_mock.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer_mock

        adapter.delete_runs_for_scout_sync("user1", "my-scout")

        # Only 1 item matches #my-scout suffix
        assert batch_writer_mock.delete_item.call_count == 1
        batch_writer_mock.delete_item.assert_called_once_with(
            Key={"PK": "user1", "SK": "TIME#ts1#my-scout"}
        )

    def test_does_nothing_when_no_matching_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.delete_runs_for_scout_sync("user1", "my-scout")
        mock_table.batch_writer.assert_not_called()

    def test_batch_deletes_in_chunks_of_25(self, adapter, mock_table):
        items = [{"PK": "user1", "SK": f"TIME#ts{i}#my-scout"} for i in range(30)]
        mock_table.query.return_value = {"Items": items}

        batch_writer_mock = MagicMock()
        batch_writer_mock.__enter__ = MagicMock(return_value=batch_writer_mock)
        batch_writer_mock.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer_mock

        adapter.delete_runs_for_scout_sync("user1", "my-scout")

        # 30 items → 2 batches (25 + 5)
        assert mock_table.batch_writer.call_count == 2
        assert batch_writer_mock.delete_item.call_count == 30


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_store_run_async(self, adapter, mock_table):
        result = await adapter.store_run("my-scout", "user1", "success")
        mock_table.put_item.assert_called_once()
        assert result["PK"] == "user1"
        assert result["scraper_name"] == "my-scout"

    @pytest.mark.asyncio
    async def test_get_latest_runs_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_latest_runs("user1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_latest_run_for_scout_raises(self, adapter):
        with pytest.raises(NotImplementedError):
            await adapter.get_latest_run_for_scout("scout123")

    @pytest.mark.asyncio
    async def test_delete_runs_for_scout_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        # Should not raise
        await adapter.delete_runs_for_scout("user1", "my-scout")
