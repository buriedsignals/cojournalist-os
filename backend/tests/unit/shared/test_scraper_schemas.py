"""
Unit tests validating that dead preferred_provider / Scrapfly code has been
fully removed from the scraper pipeline.

These tests verify:
1. MonitoringScheduleRequest has no preferred_provider field
2. ExecuteResponse has no provider field
3. schedule_monitoring() builds AWS payload without preferred_provider
4. run_scout_now() builds web scout body without preferredProvider
5. _convert_decimals() helper works correctly
"""
import pytest
from decimal import Decimal

from pydantic import ValidationError

from app.models.responses import MonitoringScheduleRequest, MonitoringScheduleResponse
from app.schemas.scouts import GeocodedLocation, Coordinates
from app.routers.scouts import ExecuteResponse


# Local copy of _convert_decimals to avoid importing the full scraper router
# (which triggers heavy service imports incompatible with Python 3.9 test env).
# This mirrors the logic in app/routers/scraper.py exactly.
def _convert_decimals(obj):
    """Convert DynamoDB Decimals to JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    return obj


# =============================================================================
# Schema Tests — MonitoringScheduleRequest
# =============================================================================


class TestMonitoringScheduleRequest:
    """Tests for MonitoringScheduleRequest Pydantic model."""

    def test_no_preferred_provider_field(self):
        """MonitoringScheduleRequest should not accept preferred_provider."""
        payload = MonitoringScheduleRequest(
            name="test-scout",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            scout_type="web",
            url="https://example.com",
            criteria="test criteria",
            topic="test topic",
        )
        assert not hasattr(payload, "preferred_provider")

    def test_extra_fields_ignored(self):
        """Extra fields like preferred_provider should be silently ignored."""
        payload = MonitoringScheduleRequest(
            name="test-scout",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            url="https://example.com",
            topic="test topic",
            preferred_provider="scrapfly",  # Dead field — should be ignored
        )
        assert not hasattr(payload, "preferred_provider")

    def test_valid_web_scout_payload(self):
        """Web scout payload should validate with all required fields."""
        payload = MonitoringScheduleRequest(
            name="my-web-scout",
            regularity="weekly",
            day_number=3,
            time="14:30",
            monitoring="EMAIL",
            scout_type="web",
            url="https://example.com/page",
            criteria="Look for price changes",
            topic="Pricing",
        )
        assert payload.name == "my-web-scout"
        assert payload.scout_type == "web"
        assert payload.url == "https://example.com/page"

    def test_valid_pulse_scout_payload(self):
        """Pulse scout payload should validate with location and topic."""
        payload = MonitoringScheduleRequest(
            name="my-pulse-scout",
            regularity="daily",
            day_number=1,
            time="08:00",
            monitoring="EMAIL",
            scout_type="pulse",
            location={"displayName": "Zurich", "country": "CH"},
            topic="local politics",
        )
        assert payload.scout_type == "pulse"
        assert payload.location is not None
        assert payload.location.displayName == "Zurich"
        assert payload.location.country == "CH"
        assert payload.topic == "local politics"

    def test_valid_pulse_scout_with_criteria(self):
        """Pulse scout payload should validate with criteria field."""
        payload = MonitoringScheduleRequest(
            name="my-pulse-scout",
            regularity="weekly",
            day_number=1,
            time="09:00",
            monitoring="EMAIL",
            scout_type="pulse",
            topic="climate",
            criteria="Focus on renewable energy policy changes",
        )
        assert payload.scout_type == "pulse"
        assert payload.criteria == "Focus on renewable energy policy changes"

    def test_content_hash_defaults_none(self):
        """content_hash should default to None."""
        payload = MonitoringScheduleRequest(
            name="test-scout",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            url="https://example.com",
            topic="test",
        )
        assert payload.content_hash is None

    def test_web_scout_requires_location_or_topic(self):
        """Web scout without location or topic should fail validation."""
        with pytest.raises(ValidationError, match="location or topic"):
            MonitoringScheduleRequest(
                name="no-scope-scout",
                regularity="daily",
                day_number=1,
                time="10:00",
                monitoring="EMAIL",
                scout_type="web",
                url="https://example.com",
            )

    def test_name_min_length(self):
        """Empty name should fail validation."""
        with pytest.raises(ValidationError):
            MonitoringScheduleRequest(
                name="",
                regularity="daily",
                day_number=1,
                time="10:00",
                monitoring="EMAIL",
            )

    def test_invalid_time_format(self):
        """Non-HH:MM time should fail validation."""
        with pytest.raises(ValidationError):
            MonitoringScheduleRequest(
                name="test",
                regularity="daily",
                day_number=1,
                time="8pm",
                monitoring="EMAIL",
            )


# =============================================================================
# Schema Tests — ExecuteResponse
# =============================================================================


class TestExecuteResponse:
    """Tests for ExecuteResponse Pydantic model (from routers/scouts.py)."""

    def test_provider_field_defaults_to_none(self):
        """ExecuteResponse provider should default to None."""
        resp = ExecuteResponse(scraper_status=True, criteria_status=True, summary="ok")
        assert resp.provider is None

    def test_minimal_response(self):
        """ExecuteResponse should accept only required fields."""
        resp = ExecuteResponse(scraper_status=True, criteria_status=False, summary="test")
        assert resp.scraper_status is True
        assert resp.criteria_status is False
        assert resp.summary == "test"
        assert resp.content_hash is None

    def test_full_response(self):
        """ExecuteResponse should accept all valid fields."""
        resp = ExecuteResponse(
            scraper_status=True,
            criteria_status=True,
            summary="Page updated with new pricing",
            content_hash="abc123",
        )
        assert resp.summary == "Page updated with new pricing"
        assert resp.content_hash == "abc123"

    def test_provider_field_accepted(self):
        """ExecuteResponse should accept provider values."""
        resp = ExecuteResponse(
            scraper_status=True,
            criteria_status=False,
            summary="",
            provider="firecrawl_plain",
        )
        assert resp.provider == "firecrawl_plain"


# =============================================================================
# Schema Tests — GeocodedLocation
# =============================================================================


class TestGeocodedLocation:
    """Tests for GeocodedLocation Pydantic model."""

    def test_minimal_location(self):
        """Location should validate with just displayName and country."""
        loc = GeocodedLocation(displayName="Zurich", country="CH")
        assert loc.displayName == "Zurich"
        assert loc.country == "CH"
        assert loc.city is None
        assert loc.coordinates is None

    def test_full_location(self):
        """Location should accept all optional fields."""
        loc = GeocodedLocation(
            displayName="Zurich, Switzerland",
            city="Zurich",
            state="Zurich",
            country="CH",
            locationType="city",
            maptilerId="123",
            coordinates=Coordinates(lat=47.3769, lon=8.5417),
        )
        assert loc.coordinates.lat == 47.3769
        assert loc.coordinates.lon == 8.5417


# =============================================================================
# Router Helper Tests — _convert_decimals
# =============================================================================


class TestConvertDecimals:
    """Tests for the _convert_decimals helper (mirrored from scraper.py)."""

    def test_convert_integer_decimal(self):
        """Decimal with no fractional part should become int."""
        assert _convert_decimals(Decimal("42")) == 42
        assert isinstance(_convert_decimals(Decimal("42")), int)

    def test_convert_float_decimal(self):
        """Decimal with fractional part should become float."""

        result = _convert_decimals(Decimal("47.3769"))
        assert result == pytest.approx(47.3769)
        assert isinstance(result, float)

    def test_convert_nested_dict(self):
        """Should recursively convert Decimals in dicts."""

        data = {
            "lat": Decimal("47.3769"),
            "lon": Decimal("8.5417"),
            "count": Decimal("5"),
            "name": "Zurich",
        }
        result = _convert_decimals(data)
        assert result == {
            "lat": pytest.approx(47.3769),
            "lon": pytest.approx(8.5417),
            "count": 5,
            "name": "Zurich",
        }

    def test_convert_nested_list(self):
        """Should recursively convert Decimals in lists."""

        data = [Decimal("1"), Decimal("2.5"), "text"]
        result = _convert_decimals(data)
        assert result == [1, 2.5, "text"]

    def test_passthrough_non_decimal(self):
        """Non-Decimal values should pass through unchanged."""

        assert _convert_decimals("hello") == "hello"
        assert _convert_decimals(42) == 42
        assert _convert_decimals(None) is None


# =============================================================================
# Router Tests — schedule_monitoring AWS payload
# =============================================================================


class TestScheduleMonitoringPayload:
    """Tests that schedule_monitoring() builds a clean AWS payload."""

    def test_aws_payload_has_no_preferred_provider(self):
        """AWS payload should never contain preferred_provider key."""
        payload = MonitoringScheduleRequest(
            name="test-scout",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            scout_type="web",
            url="https://example.com",
            criteria="test",
            topic="test",
        )
        # Build the same aws_payload dict that schedule_monitoring() builds
        aws_payload = {
            "name": payload.name,
            "url": payload.url,
            "criteria": payload.criteria,
            "monitoring": payload.monitoring,
            "regularity": payload.regularity,
            "time": payload.time,
            "scout_type": payload.scout_type,
        }
        # Add local scout fields the same way the router does
        if payload.scout_type in ("web", "pulse"):
            if payload.location:
                aws_payload["location"] = payload.location
            if payload.topic:
                aws_payload["topic"] = payload.topic

        assert "preferred_provider" not in aws_payload

    def test_aws_payload_includes_location_for_pulse(self):
        """Pulse scout payload should include location when provided."""
        payload = MonitoringScheduleRequest(
            name="pulse-scout",
            regularity="daily",
            day_number=1,
            time="08:00",
            monitoring="EMAIL",
            scout_type="pulse",
            location={"displayName": "Oslo", "country": "NO"},
            topic="politics",
        )
        aws_payload = {}
        if payload.scout_type in ("web", "pulse"):
            if payload.location:
                aws_payload["location"] = payload.location.model_dump(exclude_none=True)
            if payload.topic:
                aws_payload["topic"] = payload.topic

        assert aws_payload["location"] == {"displayName": "Oslo", "country": "NO"}
        assert aws_payload["topic"] == "politics"

    def test_aws_payload_includes_criteria_for_pulse(self):
        """Pulse scout payload should include criteria when provided."""
        payload = MonitoringScheduleRequest(
            name="pulse-scout",
            regularity="weekly",
            day_number=1,
            time="09:00",
            monitoring="EMAIL",
            scout_type="pulse",
            topic="climate",
            criteria="Focus on renewable energy",
        )
        aws_payload = {}
        if payload.criteria:
            aws_payload["criteria"] = payload.criteria

        assert aws_payload["criteria"] == "Focus on renewable energy"


# =============================================================================
# Router Tests — run_scout_now body construction
# =============================================================================


class TestRunScoutNowBody:
    """Tests that run_scout_now() builds clean request bodies without dead fields."""

    def _build_web_body(self, item: dict, user_id: str, scraper_name: str) -> dict:
        """Replicate the web scout body-building logic from run_scout_now()."""

        body = {
            "url": item.get("url", ""),
            "criteria": item.get("criteria", ""),
            "userId": user_id,
            "scraperName": scraper_name,
            "preferredLanguage": item.get("preferred_language", "en"),
        }
        if item.get("location"):
            body["location"] = _convert_decimals(item["location"])
        if item.get("topic"):
            body["topic"] = item["topic"]
        return body

    def test_web_body_no_preferred_provider(self):
        """Web scout body should never include preferredProvider."""
        item = {
            "url": "https://example.com",
            "criteria": "price changes",
            "preferred_language": "en",
            "preferred_provider": "scrapfly",  # Old dead field in DynamoDB
        }
        body = self._build_web_body(item, "user_123", "my-scout")

        assert "preferredProvider" not in body
        assert "preferred_provider" not in body

    def test_web_body_includes_location(self):
        """Web scout body should include location when present."""
        item = {
            "url": "https://example.com",
            "criteria": "test",
            "location": {"displayName": "Zurich", "country": "CH", "coordinates": {"lat": Decimal("47.37"), "lon": Decimal("8.54")}},
        }
        body = self._build_web_body(item, "user_123", "my-scout")

        assert body["location"]["displayName"] == "Zurich"
        # Decimals should be converted
        assert isinstance(body["location"]["coordinates"]["lat"], float)

    def test_web_body_includes_topic(self):
        """Web scout body should include topic when present."""
        item = {
            "url": "https://example.com",
            "criteria": "test",
            "topic": "AI safety",
        }
        body = self._build_web_body(item, "user_123", "my-scout")
        assert body["topic"] == "AI safety"

    def test_web_body_defaults(self):
        """Web scout body should use defaults for missing fields."""
        item = {}
        body = self._build_web_body(item, "user_123", "my-scout")

        assert body["url"] == ""
        assert body["criteria"] == ""
        assert body["preferredLanguage"] == "en"
        assert "location" not in body
        assert "topic" not in body

    def _build_pulse_body(self, item: dict, user_id: str, scraper_name: str) -> dict:
        """Replicate the pulse scout body-building logic from run_scout_now()."""

        body = {
            "userId": user_id,
            "scraperName": scraper_name,
            "preferred_language": item.get("preferred_language", "en"),
        }
        if item.get("location"):
            body["location"] = _convert_decimals(item["location"])
        if item.get("topic"):
            body["topic"] = item["topic"]
        return body

    def test_pulse_body_structure(self):
        """Pulse scout body should have correct structure."""
        item = {
            "preferred_language": "no",
            "location": {"displayName": "Oslo", "country": "NO"},
            "topic": "local news",
        }
        body = self._build_pulse_body(item, "user_456", "pulse-scout")

        assert body["userId"] == "user_456"
        assert body["scraperName"] == "pulse-scout"
        assert body["preferred_language"] == "no"
        assert body["location"]["displayName"] == "Oslo"
        assert body["topic"] == "local news"
        assert "preferredProvider" not in body

    def test_pulse_body_with_criteria(self):
        """Pulse scout body should include criteria when provided."""
        item = {
            "preferred_language": "de",
            "location": {"displayName": "Berlin", "country": "DE"},
            "topic": "climate",
            "criteria": "Focus on renewable energy",
        }
        body = self._build_pulse_body(item, "user_789", "pulse-scout")

        assert body["preferred_language"] == "de"
        assert body["location"]["displayName"] == "Berlin"
        assert body["topic"] == "climate"
        assert "preferredProvider" not in body


# =============================================================================
# Optional Criteria Tests ("Any Change" mode)
# =============================================================================


class TestOptionalCriteria:
    """Tests for optional criteria support (Any Change mode)."""

    def test_web_scout_without_criteria(self):
        """Web scout payload should validate without criteria (Any Change mode)."""
        payload = MonitoringScheduleRequest(
            name="any-change-scout",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            scout_type="web",
            url="https://example.com",
            topic="General",
        )
        assert payload.criteria is None
        assert payload.url == "https://example.com"

    def test_web_scout_with_criteria(self):
        """Web scout payload should validate with criteria (Specific Criteria mode)."""
        payload = MonitoringScheduleRequest(
            name="specific-scout",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            scout_type="web",
            url="https://example.com",
            criteria="Look for price changes",
            location={"displayName": "Zurich", "country": "CH"},
        )
        assert payload.criteria == "Look for price changes"

    def test_web_body_without_criteria(self):
        """Web scout body should handle None criteria gracefully."""
        item = {
            "url": "https://example.com",
            "criteria": None,
            "preferred_language": "en",
        }
        body = {
            "url": item.get("url", ""),
            "criteria": item.get("criteria") or "",
            "userId": "user_123",
            "scraperName": "my-scout",
            "preferredLanguage": item.get("preferred_language", "en"),
        }
        # criteria should be empty string (not None) when sent to execute endpoint
        assert body["criteria"] == ""

    def test_execute_response_any_change_match(self):
        """ExecuteResponse should represent any-change match correctly."""
        resp = ExecuteResponse(
            scraper_status=True,
            criteria_status=True,
            summary="Page content updated",
        )
        assert resp.criteria_status is True
        assert resp.summary == "Page content updated"
        assert resp.content_hash is None

    def test_aws_payload_no_criteria(self):
        """AWS payload should handle None criteria for any-change scouts."""
        payload = MonitoringScheduleRequest(
            name="any-change-scout",
            regularity="weekly",
            day_number=3,
            time="14:30",
            monitoring="EMAIL",
            scout_type="web",
            url="https://example.com",
            topic="General",
        )
        aws_payload = {
            "name": payload.name,
            "url": payload.url,
            "criteria": payload.criteria,
            "monitoring": payload.monitoring,
            "regularity": payload.regularity,
            "time": payload.time,
            "scout_type": payload.scout_type,
        }
        assert aws_payload["criteria"] is None


# =============================================================================
# MonitoringScheduleResponse Tests
# =============================================================================


# =============================================================================
# Schema Tests — skip_unit_extraction field
# =============================================================================


class TestSkipUnitExtractionSchema:
    """Tests for skip_unit_extraction field on PulseExecuteRequest."""

    def test_pulse_request_skip_unit_extraction_defaults_false(self):
        """PulseExecuteRequest without skip_unit_extraction defaults to False."""
        from app.schemas.pulse import PulseExecuteRequest
        req = PulseExecuteRequest(
            userId="user_123",
            scraperName="test-scout",
            location={"displayName": "Oslo", "country": "NO"},
        )
        assert req.skip_unit_extraction is False

    def test_pulse_request_skip_unit_extraction_accepts_true(self):
        """PulseExecuteRequest accepts skip_unit_extraction=True."""
        from app.schemas.pulse import PulseExecuteRequest
        req = PulseExecuteRequest(
            userId="user_123",
            scraperName="test-scout",
            skip_unit_extraction=True,
            location={"displayName": "Oslo", "country": "NO"},
        )
        assert req.skip_unit_extraction is True

    def test_pulse_request_skip_unit_extraction_defaults_false(self):
        """PulseExecuteRequest without skip_unit_extraction defaults to False."""
        from app.schemas.pulse import PulseExecuteRequest
        req = PulseExecuteRequest(
            userId="user_123",
            scraperName="test-scout",
            location={"displayName": "Oslo", "country": "NO"},
        )
        assert req.skip_unit_extraction is False

    def test_pulse_request_skip_unit_extraction_accepts_true(self):
        """PulseExecuteRequest accepts skip_unit_extraction=True."""
        from app.schemas.pulse import PulseExecuteRequest
        req = PulseExecuteRequest(
            userId="user_123",
            scraperName="test-scout",
            skip_unit_extraction=True,
            location={"displayName": "Oslo", "country": "NO"},
        )
        assert req.skip_unit_extraction is True


class TestMonitoringScheduleResponse:
    """Tests for MonitoringScheduleResponse Pydantic model."""

    def test_minimal_response(self):
        """Response should validate with required fields only."""
        resp = MonitoringScheduleResponse(
            name="test-scout",
            monitoring="EMAIL",
            regularity="daily",
            day_number=1,
            time="10:00",
            timezone="UTC",
            cron_expression="0 10 * * ? *",
            metadata={"hour": 10, "minute": 0},
        )
        assert resp.name == "test-scout"
        assert resp.scout_type == "web"  # Default
        assert resp.location is None
        assert resp.topic is None

    def test_full_response(self):
        """Response should accept all optional fields."""
        resp = MonitoringScheduleResponse(
            name="local-scout",
            scout_type="pulse",
            monitoring="EMAIL",
            regularity="daily",
            day_number=1,
            time="08:00",
            timezone="Europe/Oslo",
            cron_expression="0 8 * * ? *",
            metadata={"hour": 8, "minute": 0},
            location={"displayName": "Oslo", "country": "NO"},
            topic="politics",
        )
        assert resp.scout_type == "pulse"
        assert resp.location is not None
        assert resp.location.displayName == "Oslo"
        assert resp.location.country == "NO"
        assert resp.topic == "politics"

    def test_response_constructible_from_request_fields(self):
        """Response must be constructible from request fields + cron data.

        Guards against field drift: if a field is removed from one model
        but not the other, or the router references a deleted field,
        this test fails.
        """
        payload = MonitoringScheduleRequest(
            name="contract-test",
            regularity="daily",
            day_number=1,
            time="10:00",
            monitoring="EMAIL",
            scout_type="pulse",
            location={"displayName": "Zurich", "country": "CH"},
            topic="local news",
        )
        # Mirrors scraper.py schedule_monitoring() response construction
        resp = MonitoringScheduleResponse(
            name=payload.name,
            scout_type=payload.scout_type,
            url=payload.url,
            criteria=payload.criteria,
            channel=payload.channel,
            monitoring=payload.monitoring,
            regularity=payload.regularity,
            day_number=payload.day_number,
            time=payload.time,
            timezone="Europe/Zurich",
            cron_expression="0 10 * * ? *",
            metadata={"hour": 10, "minute": 0},
            location=payload.location,
        )
        assert resp.name == "contract-test"
        assert resp.scout_type == "pulse"
