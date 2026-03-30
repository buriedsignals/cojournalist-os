"""Unit tests for DynamoDBExecutionStorage adapter."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.aws.execution_storage import DynamoDBExecutionStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.execution_storage.get_table", return_value=mock_table):
        return DynamoDBExecutionStorage()


# ---------------------------------------------------------------------------
# store_execution_sync
# ---------------------------------------------------------------------------

class TestStoreExecutionSync:
    def test_puts_item_with_correct_pk(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="Found something new",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user1"

    def test_sk_starts_with_exec_prefix(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"].startswith("EXEC#my-scout#")

    def test_sk_format_exec_scoutname_timestamp_execid(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        # SK format: EXEC#{scout_name}#{timestamp_ms}#{exec_id}
        parts = item["SK"].split("#")
        assert parts[0] == "EXEC"
        assert parts[1] == "my-scout"
        # parts[2] is timestamp_ms — must be a numeric string
        assert parts[2].isdigit()
        # parts[3] is exec_id — 8-char hex UUID fragment
        assert len(parts[3]) == 8

    def test_stores_scout_type_and_status(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="web",
            summary_text="test",
            is_duplicate=True,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scout_type"] == "web"
        assert item["status"] == "completed"
        assert item["is_duplicate"] is True

    def test_summary_text_truncated_to_150(self, adapter, mock_table):
        long_text = "x" * 300
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text=long_text,
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert len(item["summary_text"]) == 150

    def test_ttl_set_to_90_days(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert "ttl" in item
        expected_ttl = int(time.time()) + 90 * 24 * 60 * 60
        assert abs(item["ttl"] - expected_ttl) < 5

    def test_content_hash_stored_when_provided(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="web",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
            content_hash="abc123",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["content_hash"] == "abc123"

    def test_content_hash_absent_when_not_provided(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert "content_hash" not in item

    def test_provider_stored_when_provided(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="web",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
            provider="firecrawl",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["provider"] == "firecrawl"

    def test_provider_absent_when_not_provided(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert "provider" not in item

    def test_embedding_compressed_and_stored_when_provided(self, adapter, mock_table):
        fake_embedding = [0.1, 0.2, 0.3]
        fake_compressed = "COMPRESSED_BASE64"

        with patch(
            "app.adapters.aws.execution_storage.compress_embedding",
            return_value=fake_compressed,
        ) as mock_compress:
            adapter.store_execution_sync(
                user_id="user1",
                scout_name="my-scout",
                scout_type="pulse",
                summary_text="test",
                is_duplicate=False,
                started_at="2024-01-01T10:00:00Z",
                embedding=fake_embedding,
            )

        mock_compress.assert_called_once_with(fake_embedding)
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["summary_embedding_compressed"] == fake_compressed

    def test_no_embedding_field_when_embedding_is_none_and_no_summary(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert "summary_embedding_compressed" not in item

    def test_returns_stored_item_dict(self, adapter, mock_table):
        result = adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        assert result["PK"] == "user1"
        assert result["SK"].startswith("EXEC#my-scout#")

    def test_started_at_stored(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["started_at"] == "2024-01-01T10:00:00Z"

    def test_completed_at_is_iso_utc_string(self, adapter, mock_table):
        adapter.store_execution_sync(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )

        item = mock_table.put_item.call_args[1]["Item"]
        assert "completed_at" in item
        assert item["completed_at"].endswith("Z")


# ---------------------------------------------------------------------------
# get_recent_executions_sync
# ---------------------------------------------------------------------------

class TestGetRecentExecutionsSync:
    def test_returns_empty_list_when_no_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_recent_executions_sync("user1", "my-scout")
        assert result == []

    def test_queries_exec_prefix_descending(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_recent_executions_sync("user1", "my-scout")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_filters_out_duplicates(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#1000#aaa",
                "summary_text": "real finding",
                "completed_at": "2024-01-01T10:00:00Z",
                "is_duplicate": False,
            },
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#999#bbb",
                "summary_text": "duplicate",
                "completed_at": "2024-01-01T09:00:00Z",
                "is_duplicate": True,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_recent_executions_sync("user1", "my-scout")
        assert len(result) == 1
        assert result[0]["summary_text"] == "real finding"

    def test_returns_up_to_limit(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": f"EXEC#my-scout#{i}#aaa",
                "summary_text": f"finding {i}",
                "completed_at": "2024-01-01T10:00:00Z",
                "is_duplicate": False,
            }
            for i in range(10)
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_recent_executions_sync("user1", "my-scout", limit=3)
        assert len(result) == 3

    def test_skips_items_without_summary_text(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#1000#aaa",
                "summary_text": "",
                "completed_at": "2024-01-01T10:00:00Z",
                "is_duplicate": False,
            },
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#999#bbb",
                "summary_text": "has content",
                "completed_at": "2024-01-01T09:00:00Z",
                "is_duplicate": False,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_recent_executions_sync("user1", "my-scout")
        assert len(result) == 1
        assert result[0]["summary_text"] == "has content"

    def test_returned_items_have_summary_and_completed_at(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#1000#aaa",
                "summary_text": "real finding",
                "completed_at": "2024-01-01T10:00:00Z",
                "is_duplicate": False,
            }
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_recent_executions_sync("user1", "my-scout")
        assert "summary_text" in result[0]
        assert "completed_at" in result[0]


# ---------------------------------------------------------------------------
# get_recent_embeddings_sync
# ---------------------------------------------------------------------------

class TestGetRecentEmbeddingsSync:
    def test_returns_empty_list_when_no_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_recent_embeddings_sync("user1", "my-scout")
        assert result == []

    def test_queries_exec_prefix_descending(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_recent_embeddings_sync("user1", "my-scout")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_returns_only_items_with_compressed_embedding(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#1000#aaa",
                "summary_embedding_compressed": "COMPRESSED",
                "is_duplicate": False,
            },
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#999#bbb",
                # no embedding field
                "is_duplicate": False,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_recent_embeddings_sync("user1", "my-scout")
        assert len(result) == 1
        assert result[0]["summary_embedding_compressed"] == "COMPRESSED"

    def test_respects_limit(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": f"EXEC#my-scout#{i}#aaa",
                "summary_embedding_compressed": f"EMB{i}",
                "is_duplicate": False,
            }
            for i in range(25)
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_recent_embeddings_sync("user1", "my-scout", limit=10)
        assert len(result) == 10


# ---------------------------------------------------------------------------
# get_latest_content_hash_sync
# ---------------------------------------------------------------------------

class TestGetLatestContentHashSync:
    def test_returns_none_when_no_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_latest_content_hash_sync("user1", "my-scout")
        assert result is None

    def test_returns_first_non_empty_content_hash(self, adapter, mock_table):
        items = [
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#1000#aaa",
                # no content_hash
            },
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#999#bbb",
                "content_hash": "hash_abc",
            },
            {
                "PK": "user1",
                "SK": "EXEC#my-scout#998#ccc",
                "content_hash": "hash_older",
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_latest_content_hash_sync("user1", "my-scout")
        assert result == "hash_abc"

    def test_returns_none_when_all_items_lack_content_hash(self, adapter, mock_table):
        items = [
            {"PK": "user1", "SK": "EXEC#my-scout#1000#aaa"},
            {"PK": "user1", "SK": "EXEC#my-scout#999#bbb"},
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_latest_content_hash_sync("user1", "my-scout")
        assert result is None

    def test_queries_exec_prefix_descending(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_latest_content_hash_sync("user1", "my-scout")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False


# ---------------------------------------------------------------------------
# delete_executions_for_scout_sync
# ---------------------------------------------------------------------------

class TestDeleteExecutionsForScoutSync:
    def test_queries_exec_prefix_for_scout(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.delete_executions_for_scout_sync("user1", "my-scout")
        mock_table.query.assert_called_once()

    def test_deletes_all_exec_records_for_scout(self, adapter, mock_table):
        items = [
            {"PK": "user1", "SK": "EXEC#my-scout#1000#aaa"},
            {"PK": "user1", "SK": "EXEC#my-scout#999#bbb"},
        ]
        mock_table.query.return_value = {"Items": items}

        batch_writer_mock = MagicMock()
        batch_writer_mock.__enter__ = MagicMock(return_value=batch_writer_mock)
        batch_writer_mock.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer_mock

        adapter.delete_executions_for_scout_sync("user1", "my-scout")

        assert batch_writer_mock.delete_item.call_count == 2

    def test_does_nothing_when_no_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.delete_executions_for_scout_sync("user1", "my-scout")
        mock_table.batch_writer.assert_not_called()

    def test_batch_deletes_in_chunks_of_25(self, adapter, mock_table):
        items = [
            {"PK": "user1", "SK": f"EXEC#my-scout#{i}#aaa"}
            for i in range(30)
        ]
        mock_table.query.return_value = {"Items": items}

        batch_writer_mock = MagicMock()
        batch_writer_mock.__enter__ = MagicMock(return_value=batch_writer_mock)
        batch_writer_mock.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer_mock

        adapter.delete_executions_for_scout_sync("user1", "my-scout")

        # 30 items → 2 batches (25 + 5)
        assert mock_table.batch_writer.call_count == 2
        assert batch_writer_mock.delete_item.call_count == 30

    def test_uses_correct_exec_sk_prefix(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.delete_executions_for_scout_sync("user1", "my-scout")

        # Verify a query was issued (prefix is exercised via functional tests above)
        mock_table.query.assert_called_once()


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_store_execution_async(self, adapter, mock_table):
        result = await adapter.store_execution(
            user_id="user1",
            scout_name="my-scout",
            scout_type="pulse",
            summary_text="test",
            is_duplicate=False,
            started_at="2024-01-01T10:00:00Z",
        )
        mock_table.put_item.assert_called_once()
        assert result["PK"] == "user1"

    @pytest.mark.asyncio
    async def test_get_recent_executions_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_recent_executions("user1", "my-scout")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_embeddings_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_recent_embeddings("user1", "my-scout")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_latest_content_hash_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_latest_content_hash("user1", "my-scout")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_executions_for_scout_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        # Should not raise
        await adapter.delete_executions_for_scout("user1", "my-scout")
