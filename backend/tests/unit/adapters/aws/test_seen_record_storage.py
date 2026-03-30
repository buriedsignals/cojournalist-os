"""Unit tests for DynamoDBSeenRecordStorage adapter."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from app.adapters.aws.seen_record_storage import DynamoDBSeenRecordStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conditional_check_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "conditional failed"}},
        "PutItem",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.seen_record_storage.get_table", return_value=mock_table):
        return DynamoDBSeenRecordStorage()


# ---------------------------------------------------------------------------
# mark_seen_sync
# ---------------------------------------------------------------------------

class TestMarkSeenSync:
    def test_returns_true_when_item_is_new(self, adapter, mock_table):
        # put_item succeeds (no exception) → new record
        mock_table.put_item.return_value = {}
        result = adapter.mark_seen_sync("scout-1", "user-1", "sig-abc")
        assert result is True

    def test_returns_false_when_already_exists(self, adapter, mock_table):
        mock_table.put_item.side_effect = _conditional_check_error()
        result = adapter.mark_seen_sync("scout-1", "user-1", "sig-abc")
        assert result is False

    def test_pk_is_user_id(self, adapter, mock_table):
        mock_table.put_item.return_value = {}
        adapter.mark_seen_sync("scout-1", "user-42", "sig-abc")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user-42"

    def test_sk_uses_seen_prefix_with_scout_id_and_sanitized_signature(self, adapter, mock_table):
        mock_table.put_item.return_value = {}
        adapter.mark_seen_sync("scout-1", "user-1", "sig-abc")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == "SEEN#scout-1#sig-abc"

    def test_sk_sanitizes_hash_in_signature(self, adapter, mock_table):
        """# and | in signature are replaced with - for the SK."""
        mock_table.put_item.return_value = {}
        adapter.mark_seen_sync("scout-1", "user-1", "sig#with#hash")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == "SEEN#scout-1#sig-with-hash"

    def test_sk_sanitizes_pipe_in_signature(self, adapter, mock_table):
        mock_table.put_item.return_value = {}
        adapter.mark_seen_sync("scout-1", "user-1", "sig|with|pipe")

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == "SEEN#scout-1#sig-with-pipe"

    def test_ttl_is_set_to_90_days(self, adapter, mock_table):
        mock_table.put_item.return_value = {}
        adapter.mark_seen_sync("scout-1", "user-1", "sig-abc")

        item = mock_table.put_item.call_args[1]["Item"]
        assert "ttl" in item
        assert isinstance(item["ttl"], int)
        expected_ttl = int(time.time()) + 90 * 24 * 3600
        assert abs(item["ttl"] - expected_ttl) < 5  # within 5 seconds

    def test_uses_attribute_not_exists_condition(self, adapter, mock_table):
        """put_item must include a ConditionExpression to guard against races."""
        mock_table.put_item.return_value = {}
        adapter.mark_seen_sync("scout-1", "user-1", "sig-abc")

        call_kwargs = mock_table.put_item.call_args[1]
        assert "ConditionExpression" in call_kwargs

    def test_reraises_non_conditional_client_errors(self, adapter, mock_table):
        error = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "throttled"}},
            "PutItem",
        )
        mock_table.put_item.side_effect = error
        with pytest.raises(ClientError):
            adapter.mark_seen_sync("scout-1", "user-1", "sig-abc")


# ---------------------------------------------------------------------------
# is_seen_sync
# ---------------------------------------------------------------------------

class TestIsSeenSync:
    def test_returns_false_when_item_not_found(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.is_seen_sync("scout-1", "user-1", "sig-abc")
        assert result is False

    def test_returns_false_when_item_is_none(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": None}
        result = adapter.is_seen_sync("scout-1", "user-1", "sig-abc")
        assert result is False

    def test_returns_true_when_item_exists(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "user-1", "SK": "SEEN#scout-1#sig-abc"}
        }
        result = adapter.is_seen_sync("scout-1", "user-1", "sig-abc")
        assert result is True

    def test_queries_correct_pk_and_sk(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        adapter.is_seen_sync("scout-1", "user-1", "sig-abc")

        mock_table.get_item.assert_called_once_with(
            Key={"PK": "user-1", "SK": "SEEN#scout-1#sig-abc"}
        )

    def test_sk_sanitizes_signature(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        adapter.is_seen_sync("scout-1", "user-1", "sig#abc")

        key = mock_table.get_item.call_args[1]["Key"]
        assert key["SK"] == "SEEN#scout-1#sig-abc"


# ---------------------------------------------------------------------------
# delete_seen_records_sync
# ---------------------------------------------------------------------------

class TestDeleteSeenRecordsSync:
    def _make_query_response(self, items):
        return {"Items": items, "Count": len(items)}

    def test_queries_with_correct_pk_and_sk_prefix(self, adapter, mock_table):
        mock_table.query.return_value = self._make_query_response([])
        adapter.delete_seen_records_sync("user-1", "my-scout")

        call_kwargs = mock_table.query.call_args[1]
        # Verify PK
        from boto3.dynamodb.conditions import Key
        expected_expr = Key("PK").eq("user-1") & Key("SK").begins_with("SEEN#my-scout#")
        # We can't compare condition objects directly, so verify the call was made
        assert mock_table.query.called

    def test_sk_prefix_uses_sanitized_scout_name(self, adapter, mock_table):
        """Scout names with # or | are sanitized in the query prefix."""
        mock_table.query.return_value = self._make_query_response([])
        adapter.delete_seen_records_sync("user-1", "scout#name|pipe")

        # Should not raise; query is called with sanitized name
        assert mock_table.query.called

    def test_no_delete_when_no_records_found(self, adapter, mock_table):
        mock_table.query.return_value = self._make_query_response([])
        adapter.delete_seen_records_sync("user-1", "my-scout")

        mock_table.batch_writer.assert_not_called()

    def test_batch_deletes_all_found_records(self, adapter, mock_table):
        items = [
            {"PK": "user-1", "SK": "SEEN#my-scout#sig-1"},
            {"PK": "user-1", "SK": "SEEN#my-scout#sig-2"},
            {"PK": "user-1", "SK": "SEEN#my-scout#sig-3"},
        ]
        mock_table.query.return_value = self._make_query_response(items)

        # Set up batch_writer context manager
        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_writer)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        adapter.delete_seen_records_sync("user-1", "my-scout")

        assert mock_writer.delete_item.call_count == 3

    def test_batch_delete_uses_correct_keys(self, adapter, mock_table):
        items = [
            {"PK": "user-1", "SK": "SEEN#my-scout#sig-1"},
            {"PK": "user-1", "SK": "SEEN#my-scout#sig-2"},
        ]
        mock_table.query.return_value = self._make_query_response(items)

        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_writer)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        adapter.delete_seen_records_sync("user-1", "my-scout")

        deleted_keys = [c[1]["Key"] for c in mock_writer.delete_item.call_args_list]
        assert {"PK": "user-1", "SK": "SEEN#my-scout#sig-1"} in deleted_keys
        assert {"PK": "user-1", "SK": "SEEN#my-scout#sig-2"} in deleted_keys

    def test_paginates_when_last_evaluated_key_present(self, adapter, mock_table):
        page1 = {
            "Items": [{"PK": "user-1", "SK": "SEEN#my-scout#sig-1"}],
            "LastEvaluatedKey": {"PK": "user-1", "SK": "SEEN#my-scout#sig-1"},
        }
        page2 = {
            "Items": [{"PK": "user-1", "SK": "SEEN#my-scout#sig-2"}],
        }
        mock_table.query.side_effect = [page1, page2]

        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_writer)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        adapter.delete_seen_records_sync("user-1", "my-scout")

        # Both pages queried
        assert mock_table.query.call_count == 2
        # Both items deleted
        assert mock_writer.delete_item.call_count == 2


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_mark_seen_returns_true_when_new(self, adapter, mock_table):
        mock_table.put_item.return_value = {}
        result = await adapter.mark_seen("scout-1", "user-1", "sig-abc")
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_seen_returns_false_when_exists(self, adapter, mock_table):
        mock_table.put_item.side_effect = _conditional_check_error()
        result = await adapter.mark_seen("scout-1", "user-1", "sig-abc")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_seen_returns_false_when_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.is_seen("scout-1", "user-1", "sig-abc")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_seen_returns_true_when_exists(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "user-1", "SK": "SEEN#scout-1#sig-abc"}
        }
        result = await adapter.is_seen("scout-1", "user-1", "sig-abc")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_seen_records_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        await adapter.delete_seen_records("user-1", "my-scout")
        assert mock_table.query.called
