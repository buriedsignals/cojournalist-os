"""
Tests for AI Auto-Select schemas and service (defined in export.py / export_generator.py).

Validates:
1. AutoSelectUnitInput schema field requirements and defaults
2. AutoSelectRequest validation (min/max units, optional fields)
3. AutoSelectResponse shape
4. date is optional and defaults to None (extracted by LLM as YYYY-MM-DD)
5. ExportGeneratorService.auto_select_units LLM integration

Note: Schemas are mirrored here rather than imported from app.routers.export
to avoid the module-level ExportGeneratorService import which uses Python 3.10+
syntax (str | None) incompatible with the Python 3.9 test environment.
This is the same pattern used in test_cms_export.py.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional


# ===========================================================================
# Mirrored schemas from app/routers/export.py
# (avoid importing export.py — see module docstring)
# ===========================================================================


class AutoSelectUnitInput(BaseModel):
    """Unit data for auto-selection scoring."""
    unit_id: str
    statement: str = Field(..., max_length=1000)
    entities: List[str] = Field(default=[])
    source_title: str = Field(..., max_length=500)
    created_at: str  # ISO timestamp
    date: Optional[str] = None  # Event date (YYYY-MM-DD) from LLM extraction
    unit_type: Optional[str] = "fact"
    scout_type: Optional[str] = None


class AutoSelectRequest(BaseModel):
    """Request to auto-select relevant units."""
    units: List[AutoSelectUnitInput] = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., max_length=2000)
    location: Optional[str] = Field(default=None, max_length=500)
    topic: Optional[str] = Field(default=None, max_length=200)


class AutoSelectResponse(BaseModel):
    """Response with AI-selected unit IDs."""
    selected_unit_ids: List[str]
    selection_summary: str


# =============================================================================
# AutoSelectUnitInput Schema Tests
# =============================================================================


class TestAutoSelectUnitInput:
    """Tests for AutoSelectUnitInput Pydantic model."""

    def test_valid_unit_all_fields(self):
        """Unit input should accept all fields."""
        unit = AutoSelectUnitInput(
            unit_id="unit_001",
            statement="City council approved new park budget.",
            entities=["City Council", "Park"],
            source_title="Local News Daily",
            created_at="2026-03-01T10:00:00Z",
            date="2026-03-01",
            unit_type="event",
            scout_type="pulse",
        )
        assert unit.unit_id == "unit_001"
        assert unit.statement == "City council approved new park budget."
        assert unit.entities == ["City Council", "Park"]
        assert unit.source_title == "Local News Daily"
        assert unit.created_at == "2026-03-01T10:00:00Z"
        assert unit.date == "2026-03-01"
        assert unit.unit_type == "event"
        assert unit.scout_type == "pulse"

    def test_minimal_unit_required_fields_only(self):
        """Unit input should validate with only required fields."""
        unit = AutoSelectUnitInput(
            unit_id="unit_002",
            statement="New bus route announced.",
            source_title="Transit Authority",
            created_at="2026-03-02T12:00:00Z",
        )
        assert unit.unit_id == "unit_002"
        assert unit.statement == "New bus route announced."
        assert unit.source_title == "Transit Authority"
        assert unit.created_at == "2026-03-02T12:00:00Z"

    def test_date_defaults_to_none(self):
        """date should default to None when not extracted."""
        unit = AutoSelectUnitInput(
            unit_id="unit_003",
            statement="Test statement.",
            source_title="Test Source",
            created_at="2026-03-01T00:00:00Z",
        )
        assert unit.date is None

    def test_entities_defaults_to_empty_list(self):
        """entities should default to empty list."""
        unit = AutoSelectUnitInput(
            unit_id="unit_004",
            statement="Test statement.",
            source_title="Test Source",
            created_at="2026-03-01T00:00:00Z",
        )
        assert unit.entities == []

    def test_unit_type_defaults_to_fact(self):
        """unit_type should default to 'fact'."""
        unit = AutoSelectUnitInput(
            unit_id="unit_005",
            statement="Test statement.",
            source_title="Test Source",
            created_at="2026-03-01T00:00:00Z",
        )
        assert unit.unit_type == "fact"

    def test_scout_type_defaults_to_none(self):
        """scout_type should default to None."""
        unit = AutoSelectUnitInput(
            unit_id="unit_006",
            statement="Test statement.",
            source_title="Test Source",
            created_at="2026-03-01T00:00:00Z",
        )
        assert unit.scout_type is None

    def test_rejects_missing_unit_id(self):
        """unit_id is required."""
        with pytest.raises(ValidationError):
            AutoSelectUnitInput(
                statement="Test statement.",
                source_title="Test Source",
                created_at="2026-03-01T00:00:00Z",
            )

    def test_rejects_missing_statement(self):
        """statement is required."""
        with pytest.raises(ValidationError):
            AutoSelectUnitInput(
                unit_id="unit_007",
                source_title="Test Source",
                created_at="2026-03-01T00:00:00Z",
            )

    def test_rejects_missing_source_title(self):
        """source_title is required."""
        with pytest.raises(ValidationError):
            AutoSelectUnitInput(
                unit_id="unit_008",
                statement="Test statement.",
                created_at="2026-03-01T00:00:00Z",
            )

    def test_rejects_missing_created_at(self):
        """created_at is required."""
        with pytest.raises(ValidationError):
            AutoSelectUnitInput(
                unit_id="unit_009",
                statement="Test statement.",
                source_title="Test Source",
            )

    def test_statement_max_length(self):
        """statement should reject strings longer than 1000 chars."""
        with pytest.raises(ValidationError, match="string_too_long"):
            AutoSelectUnitInput(
                unit_id="unit_010",
                statement="x" * 1001,
                source_title="Test Source",
                created_at="2026-03-01T00:00:00Z",
            )

    def test_source_title_max_length(self):
        """source_title should reject strings longer than 500 chars."""
        with pytest.raises(ValidationError, match="string_too_long"):
            AutoSelectUnitInput(
                unit_id="unit_011",
                statement="Test statement.",
                source_title="x" * 501,
                created_at="2026-03-01T00:00:00Z",
            )


# =============================================================================
# AutoSelectRequest Schema Tests
# =============================================================================


class TestAutoSelectRequest:
    """Tests for AutoSelectRequest Pydantic model."""

    def _make_unit(self, unit_id: str = "unit_001") -> dict:
        """Helper to create a valid unit dict."""
        return {
            "unit_id": unit_id,
            "statement": "Test statement.",
            "source_title": "Test Source",
            "created_at": "2026-03-01T00:00:00Z",
        }

    def test_valid_request_all_fields(self):
        """Request should accept all fields."""
        req = AutoSelectRequest(
            units=[AutoSelectUnitInput(**self._make_unit())],
            prompt="Find articles about housing policy",
            location="Oslo, Norway",
            topic="housing",
        )
        assert len(req.units) == 1
        assert req.prompt == "Find articles about housing policy"
        assert req.location == "Oslo, Norway"
        assert req.topic == "housing"

    def test_valid_request_minimal(self):
        """Request should accept only required fields."""
        req = AutoSelectRequest(
            units=[AutoSelectUnitInput(**self._make_unit())],
            prompt="Select relevant units",
        )
        assert len(req.units) == 1
        assert req.prompt == "Select relevant units"
        assert req.location is None
        assert req.topic is None

    def test_location_is_optional(self):
        """location can be None."""
        req = AutoSelectRequest(
            units=[AutoSelectUnitInput(**self._make_unit())],
            prompt="Select relevant units",
            location=None,
        )
        assert req.location is None

    def test_topic_is_optional(self):
        """topic can be None."""
        req = AutoSelectRequest(
            units=[AutoSelectUnitInput(**self._make_unit())],
            prompt="Select relevant units",
            topic=None,
        )
        assert req.topic is None

    def test_rejects_empty_units_list(self):
        """units list must have at least 1 item."""
        with pytest.raises(ValidationError, match="too_short"):
            AutoSelectRequest(
                units=[],
                prompt="Select relevant units",
            )

    def test_rejects_more_than_100_units(self):
        """units list must have at most 100 items."""
        units = [
            AutoSelectUnitInput(**self._make_unit(unit_id=f"unit_{i:03d}"))
            for i in range(101)
        ]
        with pytest.raises(ValidationError, match="too_long"):
            AutoSelectRequest(
                units=units,
                prompt="Select relevant units",
            )

    def test_accepts_exactly_100_units(self):
        """units list should accept exactly 100 items."""
        units = [
            AutoSelectUnitInput(**self._make_unit(unit_id=f"unit_{i:03d}"))
            for i in range(100)
        ]
        req = AutoSelectRequest(
            units=units,
            prompt="Select relevant units",
        )
        assert len(req.units) == 100

    def test_accepts_exactly_1_unit(self):
        """units list should accept exactly 1 item."""
        req = AutoSelectRequest(
            units=[AutoSelectUnitInput(**self._make_unit())],
            prompt="Select relevant units",
        )
        assert len(req.units) == 1

    def test_rejects_missing_prompt(self):
        """prompt is required."""
        with pytest.raises(ValidationError):
            AutoSelectRequest(
                units=[AutoSelectUnitInput(**self._make_unit())],
            )

    def test_prompt_max_length(self):
        """prompt should reject strings longer than 2000 chars."""
        with pytest.raises(ValidationError, match="string_too_long"):
            AutoSelectRequest(
                units=[AutoSelectUnitInput(**self._make_unit())],
                prompt="x" * 2001,
            )

    def test_location_max_length(self):
        """location should reject strings longer than 500 chars."""
        with pytest.raises(ValidationError, match="string_too_long"):
            AutoSelectRequest(
                units=[AutoSelectUnitInput(**self._make_unit())],
                prompt="Select",
                location="x" * 501,
            )

    def test_topic_max_length(self):
        """topic should reject strings longer than 200 chars."""
        with pytest.raises(ValidationError, match="string_too_long"):
            AutoSelectRequest(
                units=[AutoSelectUnitInput(**self._make_unit())],
                prompt="Select",
                topic="x" * 201,
            )


# =============================================================================
# AutoSelectResponse Schema Tests
# =============================================================================


class TestAutoSelectResponse:
    """Tests for AutoSelectResponse Pydantic model."""

    def test_valid_response(self):
        """Response should accept valid fields."""
        resp = AutoSelectResponse(
            selected_unit_ids=["unit_001", "unit_003"],
            selection_summary="Selected 2 units about housing policy.",
        )
        assert resp.selected_unit_ids == ["unit_001", "unit_003"]
        assert resp.selection_summary == "Selected 2 units about housing policy."

    def test_empty_selected_ids(self):
        """Response should accept empty selected_unit_ids list."""
        resp = AutoSelectResponse(
            selected_unit_ids=[],
            selection_summary="No units matched the criteria.",
        )
        assert resp.selected_unit_ids == []

    def test_rejects_missing_selected_unit_ids(self):
        """selected_unit_ids is required."""
        with pytest.raises(ValidationError):
            AutoSelectResponse(
                selection_summary="Summary",
            )

    def test_rejects_missing_selection_summary(self):
        """selection_summary is required."""
        with pytest.raises(ValidationError):
            AutoSelectResponse(
                selected_unit_ids=["unit_001"],
            )

    def test_response_serialization(self):
        """Response should serialize to dict correctly."""
        resp = AutoSelectResponse(
            selected_unit_ids=["unit_001", "unit_002"],
            selection_summary="2 units selected.",
        )
        data = resp.dict()
        assert data == {
            "selected_unit_ids": ["unit_001", "unit_002"],
            "selection_summary": "2 units selected.",
        }


# =============================================================================
# date Integration Tests
# =============================================================================


class TestDateValueExtraction:
    """Tests verifying date is optional and defaults to None.

    date is extracted by the LLM as YYYY-MM-DD event dates.
    It MUST be Optional[str] = None when not extracted.
    """

    def test_unit_without_date_in_request(self):
        """A full request should work when date is omitted."""
        req = AutoSelectRequest(
            units=[
                AutoSelectUnitInput(
                    unit_id="unit_001",
                    statement="City council met today.",
                    source_title="Local News",
                    created_at="2026-03-01T10:00:00Z",
                ),
                AutoSelectUnitInput(
                    unit_id="unit_002",
                    statement="School board voted on budget.",
                    source_title="Education Weekly",
                    created_at="2026-03-02T08:00:00Z",
                ),
            ],
            prompt="Find government meetings",
        )
        assert req.units[0].date is None
        assert req.units[1].date is None

    def test_unit_with_date_set(self):
        """date should be accepted when explicitly provided."""
        unit = AutoSelectUnitInput(
            unit_id="unit_001",
            statement="Event next week.",
            source_title="Source",
            created_at="2026-03-01T10:00:00Z",
            date="2026-03-08",
        )
        assert unit.date == "2026-03-08"

    def test_dict_conversion_includes_date_none(self):
        """dict() should include date as None when not provided."""
        unit = AutoSelectUnitInput(
            unit_id="unit_001",
            statement="Test.",
            source_title="Source",
            created_at="2026-03-01T00:00:00Z",
        )
        data = unit.dict()
        assert "date" in data
        assert data["date"] is None


# =============================================================================
# ExportGeneratorService.auto_select_units Tests
# =============================================================================

PATCH_HTTP = "app.services.export_generator.get_http_client"
PATCH_SETTINGS = "app.services.export_generator.settings"


def _make_sample_units():
    """Build a list of sample unit dicts for testing (mix of date set and None)."""
    return [
        {
            "unit_id": "unit_001",
            "statement": "City council approved new park budget of $2M on March 1.",
            "entities": ["City Council", "Park"],
            "source_title": "Local News Daily",
            "created_at": "2026-03-01T10:00:00Z",
            "date": "2026-03-01",
            "unit_type": "event",
        },
        {
            "unit_id": "unit_002",
            "statement": "School board voted on annual budget.",
            "entities": ["School Board"],
            "source_title": "Education Weekly",
            "created_at": "2026-03-02T08:00:00Z",
            "date": None,
            "unit_type": "fact",
        },
        {
            "unit_id": "unit_003",
            "statement": "New bus route connecting downtown to suburbs announced.",
            "entities": ["Transit Authority"],
            "source_title": "Transit Times",
            "created_at": "2026-03-03T14:00:00Z",
            "date": "2026-03-03",
            "unit_type": "fact",
        },
    ]


def _mock_openrouter_response(selected_ids, summary):
    """Create a mock HTTP response mimicking OpenRouter chat completion."""
    content = json.dumps({
        "selected_unit_ids": selected_ids,
        "selection_summary": summary,
    })
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return mock_response


class TestAutoSelectService:
    """Tests for ExportGeneratorService.auto_select_units method."""

    @pytest.mark.asyncio
    async def test_returns_selected_unit_ids(self):
        """Should return unit IDs from LLM response that exist in input."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        mock_response = _mock_openrouter_response(
            ["unit_001", "unit_003"],
            "Selected 2 units about city infrastructure.",
        )

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            result = await service.auto_select_units(
                units=units,
                prompt="Find articles about city infrastructure",
                location="Oslo, Norway",
            )

        assert result["selected_unit_ids"] == ["unit_001", "unit_003"]
        assert result["selection_summary"] == "Selected 2 units about city infrastructure."

    @pytest.mark.asyncio
    async def test_filters_out_hallucinated_ids(self):
        """Should discard IDs returned by LLM that are not in the input units."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        # LLM returns a mix of real and hallucinated IDs
        mock_response = _mock_openrouter_response(
            ["unit_001", "unit_999", "unit_002", "fake_id"],
            "Selected units about government.",
        )

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            result = await service.auto_select_units(
                units=units,
                prompt="Find government meetings",
            )

        # Only real IDs should survive
        assert result["selected_unit_ids"] == ["unit_001", "unit_002"]
        assert "unit_999" not in result["selected_unit_ids"]
        assert "fake_id" not in result["selected_unit_ids"]

    @pytest.mark.asyncio
    async def test_handles_empty_selection(self):
        """Should handle LLM returning no matching units."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        mock_response = _mock_openrouter_response(
            [],
            "No units matched the criteria for weather reports.",
        )

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            result = await service.auto_select_units(
                units=units,
                prompt="Find weather reports",
            )

        assert result["selected_unit_ids"] == []
        assert result["selection_summary"] == "No units matched the criteria for weather reports."

    @pytest.mark.asyncio
    async def test_prompt_includes_current_date(self):
        """System prompt sent to LLM should include the current date for recency evaluation."""
        from app.services.export_generator import ExportGeneratorService
        from datetime import datetime, timezone

        units = _make_sample_units()
        mock_response = _mock_openrouter_response(["unit_001"], "Selected 1 unit.")

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            await service.auto_select_units(
                units=units,
                prompt="Find recent news",
            )

        # Inspect the system prompt sent to OpenRouter
        call_kwargs = mock_client.post.call_args
        request_json = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
        messages = request_json["messages"]
        system_content = messages[0]["content"]

        expected_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert f"Current date: {expected_date}" in system_content

    @pytest.mark.asyncio
    async def test_handles_mixed_dates_gracefully(self):
        """Sample units with mix of date set/None should work correctly."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        # Confirm mixed date state
        assert units[0]["date"] == "2026-03-01"
        assert units[1]["date"] is None
        assert units[2]["date"] == "2026-03-03"

        mock_response = _mock_openrouter_response(
            ["unit_002"],
            "Selected 1 unit about education.",
        )

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            result = await service.auto_select_units(
                units=units,
                prompt="Find education news",
                topic="education",
            )

        assert result["selected_unit_ids"] == ["unit_002"]

    @pytest.mark.asyncio
    async def test_includes_location_and_topic_context(self):
        """When location and topic are provided, they should appear in the user prompt."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        mock_response = _mock_openrouter_response(["unit_001"], "Selected 1 unit.")

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            await service.auto_select_units(
                units=units,
                prompt="Find city budget articles",
                location="Oslo, Norway",
                topic="budget",
            )

        call_kwargs = mock_client.post.call_args
        request_json = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
        user_content = request_json["messages"][1]["content"]
        assert "Location: Oslo, Norway" in user_content
        assert "Topic: budget" in user_content

    @pytest.mark.asyncio
    async def test_no_location_or_topic_shows_fallback_context(self):
        """When neither location nor topic is given, prompt should show fallback text."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        mock_response = _mock_openrouter_response(["unit_001"], "Selected 1 unit.")

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            await service.auto_select_units(
                units=units,
                prompt="Select all",
            )

        call_kwargs = mock_client.post.call_args
        request_json = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
        user_content = request_json["messages"][1]["content"]
        assert "No specific location or topic filter." in user_content

    @pytest.mark.asyncio
    async def test_llm_response_missing_summary_uses_fallback(self):
        """If LLM omits selection_summary, a fallback summary should be generated."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        # LLM returns no selection_summary key
        content = json.dumps({"selected_unit_ids": ["unit_001", "unit_002"]})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            result = await service.auto_select_units(
                units=units,
                prompt="Select all",
            )

        assert result["selected_unit_ids"] == ["unit_001", "unit_002"]
        assert result["selection_summary"] == "2 units selected"

    @pytest.mark.asyncio
    async def test_uses_correct_model_and_temperature(self):
        """Should use gpt-4o-mini model with low temperature for deterministic selection."""
        from app.services.export_generator import ExportGeneratorService

        units = _make_sample_units()
        mock_response = _mock_openrouter_response(["unit_001"], "Selected 1 unit.")

        with patch(PATCH_HTTP, new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            service = ExportGeneratorService()
            await service.auto_select_units(
                units=units,
                prompt="Select all",
            )

        call_kwargs = mock_client.post.call_args
        request_json = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
        from app.config import settings
        assert request_json["model"] == settings.llm_model
        assert request_json["temperature"] == 0.1
        assert request_json["response_format"] == {"type": "json_object"}
        assert request_json["max_tokens"] == 1000
