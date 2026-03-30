"""Unit tests for DynamoDBPromiseStorage adapter."""
from __future__ import annotations

import hashlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.adapters.aws.promise_storage import PROCESSED_URLS_CAP, DynamoDBPromiseStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_promise(
    promise_text: str = "Build a new school by 2027",
    source_url: str = "https://council.example.com/minutes.pdf",
    source_date: str = "2025-03-01",
    context: str = "During session the mayor promised...",
    due_date: str | None = None,
    date_confidence: str = "high",
    criteria_match: bool = True,
) -> SimpleNamespace:
    """Return a duck-typed Promise object (matches app.schemas.civic.Promise)."""
    return SimpleNamespace(
        promise_text=promise_text,
        source_url=source_url,
        source_date=source_date,
        context=context,
        due_date=due_date,
        date_confidence=date_confidence,
        criteria_match=criteria_match,
    )


def _expected_promise_id(source_url: str, promise_text: str) -> str:
    return hashlib.sha256(
        f"{source_url}{promise_text}".encode()
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.promise_storage.get_table", return_value=mock_table):
        return DynamoDBPromiseStorage()


# ---------------------------------------------------------------------------
# _make_promise_id
# ---------------------------------------------------------------------------

class TestMakePromiseId:
    def test_returns_16_hex_chars(self, adapter):
        pid = adapter._make_promise_id("https://example.com", "Promise text")
        assert len(pid) == 16
        assert all(c in "0123456789abcdef" for c in pid)

    def test_no_separator_between_url_and_text(self, adapter):
        url = "https://example.com"
        text = "Promise text"
        expected = hashlib.sha256(f"{url}{text}".encode()).hexdigest()[:16]
        assert adapter._make_promise_id(url, text) == expected

    def test_different_inputs_produce_different_ids(self, adapter):
        id1 = adapter._make_promise_id("https://a.com", "Promise A")
        id2 = adapter._make_promise_id("https://b.com", "Promise B")
        assert id1 != id2

    def test_deterministic(self, adapter):
        url, text = "https://example.com", "Same promise"
        assert adapter._make_promise_id(url, text) == adapter._make_promise_id(url, text)


# ---------------------------------------------------------------------------
# store_promises_sync
# ---------------------------------------------------------------------------

class TestStorePromisesSync:
    def test_puts_one_item_per_promise(self, adapter, mock_table):
        promises = [_make_promise("Promise A"), _make_promise("Promise B")]
        adapter.store_promises_sync("user1", "scout1", promises)
        assert mock_table.put_item.call_count == 2

    def test_pk_is_user_id(self, adapter, mock_table):
        adapter.store_promises_sync("user42", "scout1", [_make_promise()])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "user42"

    def test_sk_format_is_promise_prefix_scout_id(self, adapter, mock_table):
        promise = _make_promise()
        expected_id = _expected_promise_id(promise.source_url, promise.promise_text)
        adapter.store_promises_sync("user1", "my-scout", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["SK"] == f"PROMISE#my-scout#{expected_id}"

    def test_gsi2pk_uses_due_date_when_present(self, adapter, mock_table):
        promise = _make_promise(due_date="2027-06-01")
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["GSI2PK"] == "DUEDATE#2027-06-01"

    def test_gsi2pk_is_undated_when_no_due_date(self, adapter, mock_table):
        promise = _make_promise(due_date=None)
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["GSI2PK"] == "DUEDATE#UNDATED"

    def test_gsi2sk_format(self, adapter, mock_table):
        promise = _make_promise()
        expected_id = _expected_promise_id(promise.source_url, promise.promise_text)
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["GSI2SK"] == f"user1#{expected_id}"

    def test_ttl_is_90_days_when_due_date_present(self, adapter, mock_table):
        promise = _make_promise(due_date="2027-06-01")
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        expected_ttl = int(time.time()) + 90 * 86400
        assert abs(item["ttl"] - expected_ttl) < 5

    def test_ttl_is_180_days_when_no_due_date(self, adapter, mock_table):
        promise = _make_promise(due_date=None)
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        expected_ttl = int(time.time()) + 180 * 86400
        assert abs(item["ttl"] - expected_ttl) < 5

    def test_due_date_stored_as_empty_string_when_none(self, adapter, mock_table):
        promise = _make_promise(due_date=None)
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["due_date"] == ""

    def test_status_is_pending(self, adapter, mock_table):
        adapter.store_promises_sync("user1", "scout1", [_make_promise()])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["status"] == "pending"

    def test_scout_type_is_civic(self, adapter, mock_table):
        adapter.store_promises_sync("user1", "scout1", [_make_promise()])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["scout_type"] == "civic"

    def test_schema_v_is_1(self, adapter, mock_table):
        adapter.store_promises_sync("user1", "scout1", [_make_promise()])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["schema_v"] == 1

    def test_promise_fields_stored(self, adapter, mock_table):
        promise = _make_promise(
            promise_text="Build a school",
            source_url="https://council.gov/minutes.pdf",
            source_date="2025-01-15",
            context="The mayor said...",
            date_confidence="medium",
            criteria_match=False,
        )
        adapter.store_promises_sync("user1", "scout1", [promise])
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["promise_text"] == "Build a school"
        assert item["source_url"] == "https://council.gov/minutes.pdf"
        assert item["source_date"] == "2025-01-15"
        assert item["context"] == "The mayor said..."
        assert item["date_confidence"] == "medium"
        assert item["criteria_match"] is False

    def test_no_put_when_empty_list(self, adapter, mock_table):
        adapter.store_promises_sync("user1", "scout1", [])
        mock_table.put_item.assert_not_called()


# ---------------------------------------------------------------------------
# mark_promises_notified_sync
# ---------------------------------------------------------------------------

class TestMarkPromisesNotifiedSync:
    def test_calls_update_for_each_promise_id(self, adapter, mock_table):
        adapter.mark_promises_notified_sync("user1", "scout1", ["id1", "id2", "id3"])
        assert mock_table.update_item.call_count == 3

    def test_correct_key_per_promise(self, adapter, mock_table):
        adapter.mark_promises_notified_sync("user1", "scout1", ["abc123"])
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"PK": "user1", "SK": "PROMISE#scout1#abc123"}

    def test_sets_status_to_notified(self, adapter, mock_table):
        adapter.mark_promises_notified_sync("user1", "scout1", ["abc123"])
        call_kwargs = mock_table.update_item.call_args[1]
        assert ":notified" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":notified"] == "notified"

    def test_uses_expression_attribute_names_for_status(self, adapter, mock_table):
        """status is a reserved word in DynamoDB — must be aliased."""
        adapter.mark_promises_notified_sync("user1", "scout1", ["abc123"])
        call_kwargs = mock_table.update_item.call_args[1]
        assert "#s" in call_kwargs.get("ExpressionAttributeNames", {})
        assert call_kwargs["ExpressionAttributeNames"]["#s"] == "status"

    def test_no_update_when_empty_list(self, adapter, mock_table):
        adapter.mark_promises_notified_sync("user1", "scout1", [])
        mock_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# get_stored_hash_sync
# ---------------------------------------------------------------------------

class TestGetStoredHashSync:
    def test_returns_hash_from_scraper_record(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "user1", "SK": "SCRAPER#scout1", "content_hash": "abc123"}
        }
        result = adapter.get_stored_hash_sync("user1", "scout1")
        assert result == "abc123"

    def test_returns_empty_string_when_no_item(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_stored_hash_sync("user1", "scout1")
        assert result == ""

    def test_returns_empty_string_when_hash_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": {"PK": "user1", "SK": "SCRAPER#scout1"}}
        result = adapter.get_stored_hash_sync("user1", "scout1")
        assert result == ""

    def test_queries_correct_pk_and_sk(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        adapter.get_stored_hash_sync("user42", "my-scout")
        mock_table.get_item.assert_called_once_with(
            Key={"PK": "user42", "SK": "SCRAPER#my-scout"}
        )


# ---------------------------------------------------------------------------
# get_processed_urls_sync
# ---------------------------------------------------------------------------

class TestGetProcessedUrlsSync:
    def test_returns_list_from_scraper_record(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user1",
                "SK": "SCRAPER#scout1",
                "processed_pdf_urls": ["https://a.com/doc.pdf", "https://b.com/doc.pdf"],
            }
        }
        result = adapter.get_processed_urls_sync("user1", "scout1")
        assert result == ["https://a.com/doc.pdf", "https://b.com/doc.pdf"]

    def test_returns_empty_list_when_no_item(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_processed_urls_sync("user1", "scout1")
        assert result == []

    def test_returns_empty_list_when_field_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {"Item": {"PK": "user1", "SK": "SCRAPER#scout1"}}
        result = adapter.get_processed_urls_sync("user1", "scout1")
        assert result == []

    def test_queries_correct_pk_and_sk(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        adapter.get_processed_urls_sync("user42", "my-scout")
        mock_table.get_item.assert_called_once_with(
            Key={"PK": "user42", "SK": "SCRAPER#my-scout"}
        )


# ---------------------------------------------------------------------------
# update_scraper_record_sync
# ---------------------------------------------------------------------------

class TestUpdateScraperRecordSync:
    def _setup_existing_urls(self, mock_table, urls: list[str]) -> None:
        mock_table.get_item.return_value = {
            "Item": {"processed_pdf_urls": urls}
        }

    def test_appends_new_urls_to_existing(self, adapter, mock_table):
        self._setup_existing_urls(mock_table, ["https://old.com/a.pdf"])
        adapter.update_scraper_record_sync(
            "user1", "scout1", "newhash", ["https://new.com/b.pdf"]
        )
        call_kwargs = mock_table.update_item.call_args[1]
        processed = call_kwargs["ExpressionAttributeValues"][":processed"]
        assert "https://old.com/a.pdf" in processed
        assert "https://new.com/b.pdf" in processed

    def test_stores_content_hash(self, adapter, mock_table):
        self._setup_existing_urls(mock_table, [])
        adapter.update_scraper_record_sync("user1", "scout1", "myhash", [])
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":hash"] == "myhash"

    def test_correct_key_in_update(self, adapter, mock_table):
        self._setup_existing_urls(mock_table, [])
        adapter.update_scraper_record_sync("user1", "scout1", "h", [])
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"PK": "user1", "SK": "SCRAPER#scout1"}

    def test_caps_combined_list_at_100(self, adapter, mock_table):
        existing = [f"https://old.com/{i}.pdf" for i in range(99)]
        self._setup_existing_urls(mock_table, existing)
        adapter.update_scraper_record_sync(
            "user1", "scout1", "hash", ["https://new.com/a.pdf", "https://new.com/b.pdf"]
        )
        call_kwargs = mock_table.update_item.call_args[1]
        processed = call_kwargs["ExpressionAttributeValues"][":processed"]
        assert len(processed) == PROCESSED_URLS_CAP

    def test_keeps_most_recent_entries_when_capping(self, adapter, mock_table):
        # 100 existing + 2 new = 102 total → capped to 100, oldest 2 dropped
        existing = [f"https://old.com/{i}.pdf" for i in range(100)]
        self._setup_existing_urls(mock_table, existing)
        new_urls = ["https://new.com/a.pdf", "https://new.com/b.pdf"]
        adapter.update_scraper_record_sync("user1", "scout1", "hash", new_urls)
        call_kwargs = mock_table.update_item.call_args[1]
        processed = call_kwargs["ExpressionAttributeValues"][":processed"]
        # The newest URLs should be present; the two oldest entries should be dropped
        assert "https://new.com/a.pdf" in processed
        assert "https://new.com/b.pdf" in processed
        assert "https://old.com/0.pdf" not in processed
        assert "https://old.com/1.pdf" not in processed

    def test_no_cap_when_under_100(self, adapter, mock_table):
        self._setup_existing_urls(mock_table, ["https://old.com/a.pdf"])
        adapter.update_scraper_record_sync(
            "user1", "scout1", "hash", ["https://new.com/b.pdf"]
        )
        call_kwargs = mock_table.update_item.call_args[1]
        processed = call_kwargs["ExpressionAttributeValues"][":processed"]
        assert len(processed) == 2

    def test_works_with_empty_new_list(self, adapter, mock_table):
        self._setup_existing_urls(mock_table, ["https://old.com/a.pdf"])
        adapter.update_scraper_record_sync("user1", "scout1", "hash", [])
        call_kwargs = mock_table.update_item.call_args[1]
        processed = call_kwargs["ExpressionAttributeValues"][":processed"]
        assert processed == ["https://old.com/a.pdf"]


# ---------------------------------------------------------------------------
# delete_promises_for_scout_sync
# ---------------------------------------------------------------------------

class TestDeletePromisesForScoutSync:
    def _query_response(self, items: list[dict]) -> dict:
        return {"Items": items}

    def test_queries_with_correct_sk_prefix(self, adapter, mock_table):
        mock_table.query.return_value = self._query_response([])
        adapter.delete_promises_for_scout_sync("user1", "my-scout")
        assert mock_table.query.called

    def test_no_batch_delete_when_no_records(self, adapter, mock_table):
        mock_table.query.return_value = self._query_response([])
        adapter.delete_promises_for_scout_sync("user1", "my-scout")
        mock_table.batch_writer.assert_not_called()

    def test_batch_deletes_all_found_records(self, adapter, mock_table):
        items = [
            {"PK": "user1", "SK": "PROMISE#my-scout#id1"},
            {"PK": "user1", "SK": "PROMISE#my-scout#id2"},
        ]
        mock_table.query.return_value = self._query_response(items)

        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_writer)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        adapter.delete_promises_for_scout_sync("user1", "my-scout")

        assert mock_writer.delete_item.call_count == 2

    def test_batch_delete_uses_correct_keys(self, adapter, mock_table):
        items = [
            {"PK": "user1", "SK": "PROMISE#my-scout#id1"},
            {"PK": "user1", "SK": "PROMISE#my-scout#id2"},
        ]
        mock_table.query.return_value = self._query_response(items)

        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_writer)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        adapter.delete_promises_for_scout_sync("user1", "my-scout")

        deleted_keys = [c[1]["Key"] for c in mock_writer.delete_item.call_args_list]
        assert {"PK": "user1", "SK": "PROMISE#my-scout#id1"} in deleted_keys
        assert {"PK": "user1", "SK": "PROMISE#my-scout#id2"} in deleted_keys

    def test_paginates_when_last_evaluated_key_present(self, adapter, mock_table):
        page1 = {
            "Items": [{"PK": "user1", "SK": "PROMISE#my-scout#id1"}],
            "LastEvaluatedKey": {"PK": "user1", "SK": "PROMISE#my-scout#id1"},
        }
        page2 = {
            "Items": [{"PK": "user1", "SK": "PROMISE#my-scout#id2"}],
        }
        mock_table.query.side_effect = [page1, page2]

        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_writer)
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

        adapter.delete_promises_for_scout_sync("user1", "my-scout")

        assert mock_table.query.call_count == 2
        assert mock_writer.delete_item.call_count == 2


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_store_promises_async(self, adapter, mock_table):
        await adapter.store_promises("user1", "scout1", [_make_promise()])
        assert mock_table.put_item.called

    @pytest.mark.asyncio
    async def test_mark_promises_notified_async(self, adapter, mock_table):
        await adapter.mark_promises_notified("user1", "scout1", ["id1"])
        assert mock_table.update_item.called

    @pytest.mark.asyncio
    async def test_get_stored_hash_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_stored_hash("user1", "scout1")
        assert result == ""

    @pytest.mark.asyncio
    async def test_get_processed_urls_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_processed_urls("user1", "scout1")
        assert result == []

    @pytest.mark.asyncio
    async def test_update_scraper_record_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        await adapter.update_scraper_record("user1", "scout1", "hash", [])
        assert mock_table.update_item.called

    @pytest.mark.asyncio
    async def test_delete_promises_for_scout_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        await adapter.delete_promises_for_scout("user1", "my-scout")
        assert mock_table.query.called
