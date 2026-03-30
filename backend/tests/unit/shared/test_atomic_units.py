"""
Tests for AtomicUnitService (formerly SearchDeduplicationService)

Verifies:
1. Key building for DynamoDB
2. LLM extraction prompt structure
3. End-to-end process_results flow (extraction → validation → storage)
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.atomic_unit_service import AtomicUnitService, _DATE_RE
from app.schemas.scouts import GeocodedLocation


class TestKeyBuilding:
    """Test PK/SK key building."""

    def test_pk_format_includes_user_id(self):
        """Verify PK format allows user filtering."""
        service = AtomicUnitService.__new__(AtomicUnitService)
        location = GeocodedLocation(
            displayName="Tromsø, Norway",
            city="Tromsø",
            state="Troms",
            country="NO",
            coordinates=None,
        )

        pk = service._build_pk("user_123", location)
        assert pk.startswith("USER#user_123#"), "PK must start with USER#{user_id}# for filtering"
        assert "#LOC#NO#Troms#Tromsø" in pk

    def test_sk_format(self):
        """Verify SK format."""
        service = AtomicUnitService.__new__(AtomicUnitService)
        sk = service._build_sk(1234567890, "abc-123")
        assert sk == "UNIT#1234567890#abc-123"

    def test_pk_with_missing_state(self):
        """State defaults to underscore when not provided."""
        service = AtomicUnitService.__new__(AtomicUnitService)
        location = GeocodedLocation(
            displayName="Norway",
            city=None,
            state=None,
            country="NO",
            coordinates=None,
        )

        pk = service._build_pk("user_123", location)
        assert pk == "USER#user_123#LOC#NO#_#_"


class TestServiceConfig:
    """Test service configuration."""

    def test_ttl_90_days(self):
        assert AtomicUnitService.TTL_DAYS == 90

    def test_max_units_per_article(self):
        assert AtomicUnitService.MAX_UNITS_PER_ARTICLE == 3


# ===========================================================================
# End-to-end process_results flow
# ===========================================================================

PATCH_OPENROUTER = "app.services.atomic_unit_service.openrouter_chat"
PATCH_EMBEDDINGS = "app.services.atomic_unit_service.generate_embeddings_batch"


def _mock_llm_extraction(units_json: list[dict]):
    """Return an AsyncMock that mimics openrouter_chat returning extraction JSON."""
    return AsyncMock(return_value={"content": json.dumps({"units": units_json})})


def _make_service():
    """Create AtomicUnitService with a mocked DynamoDB table and batch_writer.

    The batch_writer mock tracks all put_item calls made through the
    context manager, making them available via batch_put_item for assertions.
    """
    service = AtomicUnitService.__new__(AtomicUnitService)
    service.unit_storage = AsyncMock()
    return service


class TestProcessResultsEndToEnd:
    """Exercises real process_results → _extract_atomic_units → batch_writer chain.

    Only external services (OpenRouter, embeddings, DynamoDB) are mocked.
    Validates that units flow from LLM response through validation into storage.
    """

    @pytest.mark.asyncio
    async def test_extracts_and_stores_units_with_date(self):
        """Full flow: LLM returns units with date → validated → stored in DynamoDB."""
        service = _make_service()

        llm_units = [
            {
                "statement": "Zurich council approved CHF 50M budget on Jan 10, 2025.",
                "type": "fact",
                "entities": ["Zurich council"],
                "date": "2025-01-10",
            },
            {
                "statement": "Population grew by 12% over the past decade.",
                "type": "fact",
                "entities": ["Zurich"],
                "date": None,
            },
        ]

        location = GeocodedLocation(
            displayName="Zurich, Switzerland",
            city="Zurich", state="ZH", country="CH", coordinates=None,
        )

        # Orthogonal embeddings to avoid within-run dedup
        with patch(PATCH_OPENROUTER, _mock_llm_extraction(llm_units)), \
             patch(PATCH_EMBEDDINGS, AsyncMock(return_value=[[1.0, 0.0], [0.0, 1.0]])):

            result = await service.process_results(
                results=[{
                    "title": "Zurich Budget News",
                    "url": "https://nzz.ch/budget",
                    "content": "Zurich council approved...",
                    "summary": "Budget approved",
                    "date": "2025-01-10T08:00:00Z",
                }],
                scout_id="test-scout",
                scout_type="web",
                user_id="user_1",
                location=location,
                topic=None,
                language="English",
            )

        # Two new facts stored
        assert len(result.new_facts) == 2
        assert result.all_duplicates is False

        # First unit has date
        assert result.new_facts[0]["date"] == "2025-01-10"
        assert result.new_facts[0]["statement"].startswith("Zurich council")

        # Second unit has None date
        assert result.new_facts[1]["date"] is None

        # Units stored via adapter
        service.unit_storage.store_units.assert_called_once()
        call_args = service.unit_storage.store_units.call_args[0]
        stored_units = call_args[2]  # positional: user_id, scout_id, units
        assert len(stored_units) == 2

        # First unit has date
        assert stored_units[0]["date"] == "2025-01-10"
        assert stored_units[0]["scout_type"] == "web"

        # Second unit has None date
        assert stored_units[1]["date"] is None

    @pytest.mark.asyncio
    async def test_malformed_date_rejected(self):
        """LLM returns invalid date formats → stored as None."""
        service = _make_service()

        llm_units = [
            {
                "statement": "Event happening next week.",
                "type": "event",
                "entities": [],
                "date": "next Monday",
            },
            {
                "statement": "Budget approved in March 2025.",
                "type": "fact",
                "entities": [],
                "date": "March 2025",
            },
        ]

        # Orthogonal embeddings to avoid within-run dedup
        with patch(PATCH_OPENROUTER, _mock_llm_extraction(llm_units)), \
             patch(PATCH_EMBEDDINGS, AsyncMock(return_value=[[1.0, 0.0], [0.0, 1.0]])):

            result = await service.process_results(
                results=[{
                    "title": "Test Article",
                    "url": "https://example.com/article",
                    "content": "Test content",
                    "summary": "Test",
                }],
                scout_id="test-scout",
                scout_type="pulse",
                user_id="user_1",
                location=None,
                topic="test",
                language="English",
            )

        # Both units stored but with None date
        assert len(result.new_facts) == 2
        assert result.new_facts[0]["date"] is None
        assert result.new_facts[1]["date"] is None

        # Neither unit should have a date
        service.unit_storage.store_units.assert_called_once()
        stored_units = service.unit_storage.store_units.call_args[0][2]
        for unit in stored_units:
            assert unit["date"] is None

    @pytest.mark.asyncio
    async def test_published_date_passed_to_llm_prompt(self):
        """date from article should appear in the LLM user prompt."""
        service = _make_service()

        mock_chat = AsyncMock(return_value={
            "content": json.dumps({"units": [{
                "statement": "Test fact.", "type": "fact",
                "entities": [], "date": "2025-03-01",
            }]})
        })

        with patch(PATCH_OPENROUTER, mock_chat), \
             patch(PATCH_EMBEDDINGS, AsyncMock(return_value=[[0.1]])):

            await service.process_results(
                results=[{
                    "title": "Test",
                    "url": "https://example.com",
                    "content": "Content",
                    "summary": "Summary",
                    "date": "2025-03-01T12:00:00Z",
                }],
                scout_id="test-scout",
                scout_type="pulse",
                user_id="user_1",
                location=None,
                topic="test",
                language="English",
            )

        # Inspect the user prompt sent to openrouter_chat
        call_args = mock_chat.call_args
        messages = call_args.kwargs["messages"]
        user_prompt = messages[1]["content"]
        assert "ARTICLE PUBLISHED: 2025-03-01T12:00:00Z" in user_prompt
        assert "CURRENT DATE:" in user_prompt
