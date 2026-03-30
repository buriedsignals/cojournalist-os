"""Unit tests for DynamoDBUnitStorage adapter."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call

import pytest

from app.adapters.aws.unit_storage import DynamoDBUnitStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    return MagicMock()


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.unit_storage.get_table", return_value=mock_table):
        return DynamoDBUnitStorage()


def _make_unit(
    *,
    statement="Test fact statement",
    unit_type="fact",
    entities=None,
    source_url="https://example.com/article",
    source_domain="example.com",
    source_title="Test Article",
    country="CH",
    state="ZH",
    city="Zurich",
    topic=None,
    dataset_id=None,
    article_id="art-1",
    scout_type="pulse",
    embedding=None,
    date=None,
):
    """Build a domain unit dict matching what store_units expects."""
    unit = {
        "statement": statement,
        "unit_type": unit_type,
        "entities": entities or ["entity1"],
        "source_url": source_url,
        "source_domain": source_domain,
        "source_title": source_title,
        "article_id": article_id,
        "scout_type": scout_type,
        "used_in_article": False,
    }
    if country:
        unit["country"] = country
    if state:
        unit["state"] = state
    if city:
        unit["city"] = city
    if topic:
        unit["topic"] = topic
    if dataset_id:
        unit["dataset_id"] = dataset_id
    if embedding:
        unit["embedding"] = embedding
    if date:
        unit["date"] = date
    return unit


# ---------------------------------------------------------------------------
# store_units_sync
# ---------------------------------------------------------------------------

class TestStoreUnitsSync:
    def test_batch_writes_units(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(), _make_unit(statement="Second fact")]
        adapter.store_units_sync("user1", "scout-1", units)

        assert batch_writer.put_item.call_count == 2

    def test_builds_location_pk(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(country="CH", state="ZH", city="Zurich")]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#user1#LOC#CH#ZH#Zurich"

    def test_builds_topic_pk(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(country=None, state=None, city=None, topic="AI")]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#user1#TOPIC#AI"

    def test_builds_dataset_pk(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(country=None, state=None, city=None, dataset_id="ds-42")]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#user1#DATA#ds-42"

    def test_location_pk_uses_underscores_for_missing_state_city(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(country="US", state=None, city=None)]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#user1#LOC#US#_#_"

    def test_sk_format_unit_timestamp_id(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit()]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["SK"].startswith("UNIT#")
        parts = item["SK"].split("#")
        assert parts[0] == "UNIT"
        assert parts[1].isdigit()  # timestamp_ms
        assert len(parts[2]) > 0  # unit_id

    def test_sets_gsi_keys(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(article_id="art-123")]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        # article-units-index GSI
        assert item["GSI1PK"] == "ARTICLE#art-123"
        assert item["GSI1SK"].startswith("UNIT#")
        # scout-units-index GSI
        assert item["GSI2PK"] == "USER#user1#SCOUT#scout-1"
        assert item["GSI2SK"].startswith("UNIT#")

    def test_sets_user_id_for_user_units_index(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit()]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["user_id"] == "user1"

    def test_compresses_embedding_when_provided(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        with patch(
            "app.adapters.aws.unit_storage.compress_embedding",
            return_value="COMPRESSED",
        ) as mock_compress:
            units = [_make_unit(embedding=[0.1, 0.2, 0.3])]
            adapter.store_units_sync("user1", "scout-1", units)

        mock_compress.assert_called_once_with([0.1, 0.2, 0.3])
        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["embedding_compressed"] == "COMPRESSED"

    def test_no_embedding_field_when_none(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(embedding=None)]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert "embedding_compressed" not in item

    def test_sets_ttl_90_days(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit()]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        expected_ttl = int(time.time()) + 90 * 24 * 60 * 60
        assert abs(item["ttl"] - expected_ttl) < 5

    def test_sets_used_in_article_false(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit()]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["used_in_article"] is False

    def test_stores_topic_field_when_present(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(country=None, state=None, city=None, topic="climate")]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["topic"] == "climate"

    def test_stores_date_when_present(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit(date="2025-01-15")]
        adapter.store_units_sync("user1", "scout-1", units)

        item = batch_writer.put_item.call_args[1]["Item"]
        assert item["date"] == "2025-01-15"

    def test_handles_empty_units_list(self, adapter, mock_table):
        adapter.store_units_sync("user1", "scout-1", [])
        mock_table.batch_writer.assert_not_called()


# ---------------------------------------------------------------------------
# search_units_sync
# ---------------------------------------------------------------------------

class TestSearchUnitsSync:
    def test_returns_empty_when_no_items(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.search_units_sync("user1", [0.1, 0.2])
        assert result == []

    def test_searches_all_user_units_via_gsi(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.search_units_sync("user1", [0.1, 0.2])

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "user-units-index"

    def test_scores_and_sorts_by_cosine_similarity(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "PK": "USER#user1#LOC#CH#ZH#Zurich", "SK": "UNIT#1000#abc",
                "statement": "Low match", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1", "created_at": "2025-01-01",
                "used_in_article": False,
                "embedding_compressed": "COMPRESSED_LOW",
            },
            {
                "unit_id": "u2", "PK": "USER#user1#LOC#CH#ZH#Zurich", "SK": "UNIT#1001#def",
                "statement": "High match", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1", "created_at": "2025-01-01",
                "used_in_article": False,
                "embedding_compressed": "COMPRESSED_HIGH",
            },
        ]
        mock_table.query.return_value = {"Items": items}

        with patch("app.adapters.aws.unit_storage.decompress_embedding") as mock_decompress, \
             patch("app.adapters.aws.unit_storage.cosine_similarity") as mock_cosine:
            mock_decompress.side_effect = lambda x: [0.1, 0.2] if x == "COMPRESSED_LOW" else [0.9, 0.8]
            mock_cosine.side_effect = [0.3, 0.9]  # low, high

            result = adapter.search_units_sync("user1", [0.5, 0.5])

        assert len(result) == 2
        assert result[0]["unit_id"] == "u2"  # highest similarity first
        assert result[0]["similarity_score"] == 0.9

    def test_skips_items_without_embedding(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "PK": "pk", "SK": "sk",
                "statement": "no embedding", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1", "created_at": "2025-01-01",
                "used_in_article": False,
                # no embedding_compressed
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.search_units_sync("user1", [0.5, 0.5])
        assert result == []

    def test_skips_used_items(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "PK": "pk", "SK": "sk",
                "statement": "used", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1", "created_at": "2025-01-01",
                "used_in_article": True,
                "embedding_compressed": "COMPRESSED",
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.search_units_sync("user1", [0.5, 0.5])
        assert result == []

    def test_respects_limit(self, adapter, mock_table):
        items = [
            {
                "unit_id": f"u{i}", "PK": "pk", "SK": f"sk{i}",
                "statement": f"fact {i}", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1", "created_at": "2025-01-01",
                "used_in_article": False,
                "embedding_compressed": f"COMPRESSED_{i}",
            }
            for i in range(10)
        ]
        mock_table.query.return_value = {"Items": items}

        with patch("app.adapters.aws.unit_storage.decompress_embedding", return_value=[0.5, 0.5]), \
             patch("app.adapters.aws.unit_storage.cosine_similarity", return_value=0.8):
            result = adapter.search_units_sync("user1", [0.5, 0.5], limit=3)

        assert len(result) == 3

    def test_filters_by_location(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.search_units_sync(
            "user1", [0.5], filters={"country": "CH", "state": "ZH", "city": "Zurich"}
        )

        call_kwargs = mock_table.query.call_args[1]
        # Should query by PK, not via GSI
        assert "IndexName" not in call_kwargs

    def test_filters_by_topic(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.search_units_sync(
            "user1", [0.5], filters={"topic": "AI"}
        )

        call_kwargs = mock_table.query.call_args[1]
        assert "IndexName" not in call_kwargs


# ---------------------------------------------------------------------------
# get_units_for_article_sync
# ---------------------------------------------------------------------------

class TestGetUnitsForArticleSync:
    def test_queries_article_units_index(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_for_article_sync("art-123")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "article-units-index"

    def test_returns_unit_dicts(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "article_id": "art-123",
                "PK": "pk", "SK": "sk",
                "statement": "A fact", "unit_type": "fact",
                "entities": ["e1"], "source_url": "https://example.com",
                "source_domain": "example.com", "source_title": "Title",
                "scout_type": "pulse", "scout_id": "s1",
                "created_at": "2025-01-01", "used_in_article": False,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_units_for_article_sync("art-123")
        assert len(result) == 1
        assert result[0]["unit_id"] == "u1"
        assert result[0]["article_id"] == "art-123"

    def test_returns_empty_when_no_matches(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_units_for_article_sync("art-999")
        assert result == []


# ---------------------------------------------------------------------------
# get_units_by_location_sync
# ---------------------------------------------------------------------------

class TestGetUnitsByLocationSync:
    def test_builds_correct_pk(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_location_sync("user1", "CH", state="ZH", city="Zurich")

        call_kwargs = mock_table.query.call_args[1]
        # Check that the PK has the right location format
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert expr_values[":pk"] == "USER#user1#LOC#CH#ZH#Zurich"

    def test_uses_underscores_for_missing_components(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_location_sync("user1", "US")

        call_kwargs = mock_table.query.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert expr_values[":pk"] == "USER#user1#LOC#US#_#_"

    def test_queries_newest_first(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_location_sync("user1", "CH")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_respects_limit(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_location_sync("user1", "CH", limit=25)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 25

    def test_returns_formatted_units(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "PK": "USER#user1#LOC#CH#ZH#Zurich",
                "SK": "UNIT#1000#abc", "statement": "test",
                "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1",
                "created_at": "2025-01-01", "used_in_article": False,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_units_by_location_sync("user1", "CH", state="ZH", city="Zurich")
        assert len(result) == 1
        assert result[0]["unit_id"] == "u1"


# ---------------------------------------------------------------------------
# get_units_by_topic_sync
# ---------------------------------------------------------------------------

class TestGetUnitsByTopicSync:
    def test_builds_correct_pk(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_topic_sync("user1", "AI")

        call_kwargs = mock_table.query.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert expr_values[":pk"] == "USER#user1#TOPIC#AI"

    def test_queries_newest_first(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_topic_sync("user1", "AI")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_respects_limit(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_topic_sync("user1", "AI", limit=10)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 10

    def test_returns_formatted_units(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "PK": "USER#user1#TOPIC#AI",
                "SK": "UNIT#1000#abc", "statement": "AI fact",
                "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1",
                "created_at": "2025-01-01", "used_in_article": False,
                "topic": "AI",
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_units_by_topic_sync("user1", "AI")
        assert len(result) == 1
        assert result[0]["topic"] == "AI"


# ---------------------------------------------------------------------------
# get_distinct_locations_sync
# ---------------------------------------------------------------------------

class TestGetDistinctLocationsSync:
    def test_queries_user_units_index(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_distinct_locations_sync("user1")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "user-units-index"

    def test_extracts_unique_locations(self, adapter, mock_table):
        items = [
            {"PK": "USER#user1#LOC#CH#ZH#Zurich"},
            {"PK": "USER#user1#LOC#CH#ZH#Zurich"},  # duplicate
            {"PK": "USER#user1#LOC#US#CA#LA"},
            {"PK": "USER#user1#TOPIC#AI"},  # not a location
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_distinct_locations_sync("user1")
        assert len(result) == 2

    def test_returns_location_strings(self, adapter, mock_table):
        items = [{"PK": "USER#user1#LOC#CH#ZH#Zurich"}]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_distinct_locations_sync("user1")
        assert "CH#ZH#Zurich" in [loc["location"] for loc in result]

    def test_returns_empty_when_no_locations(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_distinct_locations_sync("user1")
        assert result == []


# ---------------------------------------------------------------------------
# get_distinct_topics_sync
# ---------------------------------------------------------------------------

class TestGetDistinctTopicsSync:
    def test_queries_user_units_index(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_distinct_topics_sync("user1")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "user-units-index"

    def test_extracts_unique_topics(self, adapter, mock_table):
        items = [
            {"PK": "USER#user1#TOPIC#AI"},
            {"PK": "USER#user1#TOPIC#AI"},  # duplicate
            {"PK": "USER#user1#TOPIC#Climate"},
            {"PK": "USER#user1#LOC#CH#ZH#Zurich"},  # not a topic
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_distinct_topics_sync("user1")
        assert sorted(result) == ["AI", "Climate"]

    def test_returns_sorted_topics(self, adapter, mock_table):
        items = [
            {"PK": "USER#user1#TOPIC#Zebra"},
            {"PK": "USER#user1#TOPIC#Apple"},
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_distinct_topics_sync("user1")
        assert result == ["Apple", "Zebra"]

    def test_returns_empty_when_no_topics(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = adapter.get_distinct_topics_sync("user1")
        assert result == []


# ---------------------------------------------------------------------------
# mark_used_sync
# ---------------------------------------------------------------------------

class TestMarkUsedSync:
    def test_updates_each_unit(self, adapter, mock_table):
        unit_ids = [("pk1", "sk1"), ("pk2", "sk2")]
        adapter.mark_used_sync(unit_ids)

        assert mock_table.update_item.call_count == 2

    def test_sets_used_in_article_true_and_ttl(self, adapter, mock_table):
        unit_ids = [("pk1", "sk1")]
        adapter.mark_used_sync(unit_ids)

        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"PK": "pk1", "SK": "sk1"}
        assert ":true" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":true"] is True
        assert ":ttl" in call_kwargs["ExpressionAttributeValues"]

    def test_ttl_set_to_60_days(self, adapter, mock_table):
        unit_ids = [("pk1", "sk1")]
        adapter.mark_used_sync(unit_ids)

        call_kwargs = mock_table.update_item.call_args[1]
        expected_ttl = int(time.time()) + 60 * 24 * 60 * 60
        actual_ttl = call_kwargs["ExpressionAttributeValues"][":ttl"]
        assert abs(actual_ttl - expected_ttl) < 5

    def test_handles_empty_list(self, adapter, mock_table):
        adapter.mark_used_sync([])
        mock_table.update_item.assert_not_called()

    def test_continues_on_error(self, adapter, mock_table):
        mock_table.update_item.side_effect = [Exception("fail"), None]
        # Should not raise
        adapter.mark_used_sync([("pk1", "sk1"), ("pk2", "sk2")])
        assert mock_table.update_item.call_count == 2


# ---------------------------------------------------------------------------
# get_all_unused_units_sync
# ---------------------------------------------------------------------------

class TestGetAllUnusedUnitsSync:
    def test_queries_user_units_index(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_all_unused_units_sync("user1")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "user-units-index"

    def test_queries_descending(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_all_unused_units_sync("user1")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_over_fetches_by_3x(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_all_unused_units_sync("user1", limit=20)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 60  # 20 * 3

    def test_over_fetch_capped_at_200(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_all_unused_units_sync("user1", limit=100)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 200

    def test_filters_out_used_units(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "PK": "pk", "SK": "sk1",
                "statement": "unused", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1",
                "created_at": "2025-01-01", "used_in_article": False,
            },
            {
                "unit_id": "u2", "PK": "pk", "SK": "sk2",
                "statement": "used", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1",
                "created_at": "2025-01-01", "used_in_article": True,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_all_unused_units_sync("user1")
        assert len(result) == 1
        assert result[0]["unit_id"] == "u1"

    def test_respects_limit_after_filtering(self, adapter, mock_table):
        items = [
            {
                "unit_id": f"u{i}", "PK": "pk", "SK": f"sk{i}",
                "statement": f"fact {i}", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "s1",
                "created_at": "2025-01-01", "used_in_article": False,
            }
            for i in range(10)
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_all_unused_units_sync("user1", limit=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# get_units_by_scout_sync
# ---------------------------------------------------------------------------

class TestGetUnitsByScoutSync:
    def test_queries_scout_units_index(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_scout_sync("user1", "scout-1")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "scout-units-index"

    def test_builds_correct_gsi2pk(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_scout_sync("user1", "scout-1")

        call_kwargs = mock_table.query.call_args[1]
        expr_values = call_kwargs["ExpressionAttributeValues"]
        assert expr_values[":gsi2pk"] == "USER#user1#SCOUT#scout-1"

    def test_queries_newest_first(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_scout_sync("user1", "scout-1")

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False

    def test_respects_limit(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.get_units_by_scout_sync("user1", "scout-1", limit=25)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 25

    def test_returns_formatted_units(self, adapter, mock_table):
        items = [
            {
                "unit_id": "u1", "article_id": "art-1",
                "PK": "USER#user1#LOC#CH#ZH#Zurich", "SK": "UNIT#1000#abc",
                "statement": "test", "unit_type": "fact", "entities": [],
                "source_url": "", "source_domain": "", "source_title": "",
                "scout_type": "pulse", "scout_id": "scout-1",
                "created_at": "2025-01-01", "used_in_article": False,
            },
        ]
        mock_table.query.return_value = {"Items": items}

        result = adapter.get_units_by_scout_sync("user1", "scout-1")
        assert len(result) == 1
        assert result[0]["unit_id"] == "u1"
        assert result[0]["scout_id"] == "scout-1"


# ---------------------------------------------------------------------------
# Async wrappers — smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_store_units_async(self, adapter, mock_table):
        batch_writer = MagicMock()
        batch_writer.__enter__ = MagicMock(return_value=batch_writer)
        batch_writer.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = batch_writer

        units = [_make_unit()]
        await adapter.store_units("user1", "scout-1", units)
        assert batch_writer.put_item.call_count == 1

    @pytest.mark.asyncio
    async def test_search_units_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.search_units("user1", [0.1, 0.2])
        assert result == []

    @pytest.mark.asyncio
    async def test_get_units_for_article_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_units_for_article("art-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_units_by_location_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_units_by_location("user1", "CH")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_units_by_topic_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_units_by_topic("user1", "AI")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_distinct_locations_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_distinct_locations("user1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_distinct_topics_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_distinct_topics("user1")
        assert result == []

    @pytest.mark.asyncio
    async def test_mark_used_async(self, adapter, mock_table):
        await adapter.mark_used([("pk1", "sk1")])
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_unused_units_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_all_unused_units("user1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_units_by_scout_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        result = await adapter.get_units_by_scout("user1", "scout-1")
        assert result == []
