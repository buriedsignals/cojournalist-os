"""Unit tests for DynamoDBPostSnapshotStorage adapter."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.aws.post_snapshot_storage import DynamoDBPostSnapshotStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.post_snapshot_storage.get_table", return_value=mock_table):
        return DynamoDBPostSnapshotStorage()


SAMPLE_POSTS = [
    {"id": "1", "text": "Hello world", "likes": 10},
    {"id": "2", "text": "Another post", "likes": 5},
]


# ---------------------------------------------------------------------------
# store_snapshot_sync
# ---------------------------------------------------------------------------

class TestStoreSnapshotSync:
    def test_puts_item_with_correct_pk(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user1"

    def test_sk_uses_posts_prefix(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == "POSTS#scout-abc"

    def test_posts_stored_as_json_string(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert isinstance(item["posts"], str)
        assert json.loads(item["posts"]) == SAMPLE_POSTS

    def test_platform_stored(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "instagram", "@instahandle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["platform"] == "instagram"

    def test_handle_stored(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@myhandle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["handle"] == "@myhandle"

    def test_post_count_matches_posts_length(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["post_count"] == len(SAMPLE_POSTS)

    def test_post_count_zero_for_empty_list(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", [])

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["post_count"] == 0

    def test_updated_at_is_iso_string_with_z(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert "updated_at" in item
        assert item["updated_at"].endswith("Z")

    def test_ttl_is_set_to_90_days(self, adapter, mock_table):
        import time
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)

        item = mock_table.put_item.call_args[1]["Item"]
        assert "ttl" in item
        assert isinstance(item["ttl"], int)
        now_ts = int(time.time())
        expected_ttl = now_ts + 90 * 24 * 3600
        assert abs(item["ttl"] - expected_ttl) < 5  # within 5 seconds

    def test_stores_empty_posts_list(self, adapter, mock_table):
        adapter.store_snapshot_sync("user1", "scout-abc", "twitter", "@handle", [])

        item = mock_table.put_item.call_args[1]["Item"]
        assert json.loads(item["posts"]) == []


# ---------------------------------------------------------------------------
# get_snapshot_sync
# ---------------------------------------------------------------------------

class TestGetSnapshotSync:
    def test_returns_none_when_item_not_found(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_snapshot_sync("user1", "scout-abc")
        assert result is None

    def test_returns_none_when_item_key_is_none(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": None}
        result = adapter.get_snapshot_sync("user1", "scout-abc")
        assert result is None

    def test_queries_correct_pk_and_sk(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        adapter.get_snapshot_sync("user1", "scout-abc")

        mock_table.get_item.assert_called_once_with(
            Key={"PK": "user1", "SK": "POSTS#scout-abc"}
        )

    def test_returns_dict_with_posts_decoded_from_json_string(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "posts": json.dumps(SAMPLE_POSTS),
                "platform": "twitter",
                "handle": "@handle",
                "post_count": 2,
            }
        }
        result = adapter.get_snapshot_sync("user1", "scout-abc")

        assert result is not None
        assert result["posts"] == SAMPLE_POSTS

    def test_handles_posts_as_raw_list(self, adapter, mock_table):
        """Older records may store posts as a raw list, not a JSON string."""
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "posts": SAMPLE_POSTS,  # raw list (legacy format)
                "platform": "twitter",
                "handle": "@handle",
                "post_count": 2,
            }
        }
        result = adapter.get_snapshot_sync("user1", "scout-abc")

        assert result is not None
        assert result["posts"] == SAMPLE_POSTS

    def test_returns_platform_and_handle(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "posts": json.dumps(SAMPLE_POSTS),
                "platform": "instagram",
                "handle": "@instauser",
                "post_count": 2,
            }
        }
        result = adapter.get_snapshot_sync("user1", "scout-abc")

        assert result["platform"] == "instagram"
        assert result["handle"] == "@instauser"

    def test_returns_stored_post_count(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "posts": json.dumps(SAMPLE_POSTS),
                "platform": "twitter",
                "handle": "@handle",
                "post_count": 2,
            }
        }
        result = adapter.get_snapshot_sync("user1", "scout-abc")
        assert result["post_count"] == 2

    def test_falls_back_to_len_posts_when_post_count_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "posts": json.dumps(SAMPLE_POSTS),
                "platform": "twitter",
                "handle": "@handle",
                # no post_count field
            }
        }
        result = adapter.get_snapshot_sync("user1", "scout-abc")
        assert result["post_count"] == len(SAMPLE_POSTS)

    def test_returns_none_on_dynamo_exception(self, adapter, mock_table):
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        result = adapter.get_snapshot_sync("user1", "scout-abc")
        assert result is None

    def test_returns_empty_posts_when_posts_field_missing(self, adapter, mock_table):
        """Missing posts field should fall back to empty list."""
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "platform": "twitter",
                "handle": "@handle",
                # no posts field
            }
        }
        result = adapter.get_snapshot_sync("user1", "scout-abc")
        assert result["posts"] == []


# ---------------------------------------------------------------------------
# delete_snapshot_sync
# ---------------------------------------------------------------------------

class TestDeleteSnapshotSync:
    def test_calls_delete_item_with_correct_key(self, adapter, mock_table):
        adapter.delete_snapshot_sync("user1", "scout-abc")

        mock_table.delete_item.assert_called_once_with(
            Key={"PK": "user1", "SK": "POSTS#scout-abc"}
        )

    def test_does_not_raise_on_dynamo_exception(self, adapter, mock_table):
        mock_table.delete_item.side_effect = Exception("DynamoDB error")
        # Should not raise
        adapter.delete_snapshot_sync("user1", "scout-abc")

    def test_deletes_using_scout_name_in_sk(self, adapter, mock_table):
        adapter.delete_snapshot_sync("user42", "my-social-scout")

        key = mock_table.delete_item.call_args[1]["Key"]
        assert key["PK"] == "user42"
        assert key["SK"] == "POSTS#my-social-scout"


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_store_snapshot_async(self, adapter, mock_table):
        await adapter.store_snapshot("user1", "scout-abc", "twitter", "@handle", SAMPLE_POSTS)
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user1"
        assert item["SK"] == "POSTS#scout-abc"

    @pytest.mark.asyncio
    async def test_get_snapshot_async_returns_none_when_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_snapshot("user1", "scout-abc")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_snapshot_async_returns_data(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "POSTS#scout-abc",
                "posts": json.dumps(SAMPLE_POSTS),
                "platform": "twitter",
                "handle": "@handle",
                "post_count": 2,
            }
        }
        result = await adapter.get_snapshot("user1", "scout-abc")
        assert result["posts"] == SAMPLE_POSTS
        assert result["platform"] == "twitter"

    @pytest.mark.asyncio
    async def test_delete_snapshot_async(self, adapter, mock_table):
        await adapter.delete_snapshot("user1", "scout-abc")
        mock_table.delete_item.assert_called_once_with(
            Key={"PK": "user1", "SK": "POSTS#scout-abc"}
        )

    @pytest.mark.asyncio
    async def test_delete_snapshot_async_suppresses_exception(self, adapter, mock_table):
        mock_table.delete_item.side_effect = Exception("DynamoDB error")
        # Should not raise
        await adapter.delete_snapshot("user1", "scout-abc")
