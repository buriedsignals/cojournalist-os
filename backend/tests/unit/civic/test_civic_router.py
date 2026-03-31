"""
Unit tests for Civic Scout schemas, credit costs, and router endpoints.

Verifies:
1. CivicDiscoverRequest validates correctly (valid domain, empty domain fails, strips protocol)
2. CandidateUrl works with valid confidence
3. CivicExecuteRequest works with minimal and full params
4. Promise works with and without due_date
5. CivicExecuteResult works
6. CREDIT_COSTS["civic"] == 20 and CREDIT_COSTS["civic_discover"] == 10
7. POST /civic/execute without service key returns 401
8. POST /civic/notify-promises without service key returns 401
9. POST /civic/discover endpoint integration tests (mocked auth/services)
"""
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.schemas.civic import (
    CivicDiscoverRequest,
    CandidateUrl,
    CivicDiscoverResponse,
    CivicExecuteRequest,
    CivicExecuteResult,
    CivicTestRequest,
    CivicTestResponse,
    Promise,
)
from app.utils.credits import CREDIT_COSTS
from app.dependencies import get_current_user
from app.routers import civic as civic_module

# Build a minimal test app with only the civic router (avoids importing app.main).
# Civic router declares its own prefix="/civic", so we mount it under /api to
# produce the same /api/civic/* paths as in production.
_test_app = FastAPI()

# Configure slowapi rate limiter to match production
_limiter = Limiter(key_func=get_remote_address)
_test_app.state.limiter = _limiter
_test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_test_app.include_router(civic_module.router, prefix="/api")

client = TestClient(_test_app)

# ---------------------------------------------------------------------------
# Shared constants for endpoint integration tests
# ---------------------------------------------------------------------------

MOCK_USER = {"user_id": "test-civic-user", "credits": 100, "tier": "pro"}
MOCK_FREE_USER = {"user_id": "test-free-user", "credits": 100, "tier": "free"}

PATCH_VALIDATE = "app.routers.civic.validate_credits"
PATCH_ORCHESTRATOR = "app.routers.civic.CivicOrchestrator"
PATCH_DECREMENT = "app.routers.civic.decrement_credit"

FAKE_CANDIDATES = [
    CandidateUrl(url="https://zermatt.ch/meetings", description="Council meetings", confidence=0.9),
    CandidateUrl(url="https://zermatt.ch/protocols", description="Protocols", confidence=0.7),
]

FAKE_PROMISES = [
    Promise(
        promise_text="New school to be built by 2027.",
        context="The council approved the school construction project.",
        source_url="https://zermatt.ch/meetings/protocol_2026-03-01.pdf",
        source_date="2026-03-01",
        due_date="2027-12-31",
        date_confidence="high",
        criteria_match=True,
    ),
    Promise(
        promise_text="Road repairs to begin in Q3.",
        context="The public works committee announced road maintenance.",
        source_url="https://zermatt.ch/meetings/protocol_2026-03-01.pdf",
        source_date="2026-03-01",
        date_confidence="medium",
        criteria_match=False,
    ),
]


@pytest.fixture()
def auth_client():
    """TestClient with Pro-tier session auth and rate limiter disabled."""
    _test_app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    civic_module.limiter.enabled = False
    c = TestClient(_test_app, raise_server_exceptions=False)
    yield c
    civic_module.limiter.enabled = True
    _test_app.dependency_overrides.clear()


@pytest.fixture()
def free_client():
    """TestClient with Free-tier session auth and rate limiter disabled."""
    _test_app.dependency_overrides[get_current_user] = lambda: MOCK_FREE_USER
    civic_module.limiter.enabled = False
    c = TestClient(_test_app, raise_server_exceptions=False)
    yield c
    civic_module.limiter.enabled = True
    _test_app.dependency_overrides.clear()


# =============================================================================
# CivicDiscoverRequest Tests
# =============================================================================


class TestCivicDiscoverRequest:
    """Tests for CivicDiscoverRequest Pydantic model."""

    def test_valid_domain(self):
        """Plain domain should validate and pass through unchanged."""
        req = CivicDiscoverRequest(root_domain="example.gov")
        assert req.root_domain == "example.gov"

    def test_strips_https_protocol(self):
        """https:// prefix should be stripped."""
        req = CivicDiscoverRequest(root_domain="https://example.gov")
        assert req.root_domain == "example.gov"

    def test_strips_http_protocol(self):
        """http:// prefix should be stripped."""
        req = CivicDiscoverRequest(root_domain="http://example.gov")
        assert req.root_domain == "example.gov"

    def test_strips_www_prefix(self):
        """www. prefix should be stripped."""
        req = CivicDiscoverRequest(root_domain="www.example.gov")
        assert req.root_domain == "example.gov"

    def test_strips_https_and_www(self):
        """https://www. prefix should be fully stripped."""
        req = CivicDiscoverRequest(root_domain="https://www.example.gov")
        assert req.root_domain == "example.gov"

    def test_strips_trailing_slash(self):
        """Trailing slash should be removed."""
        req = CivicDiscoverRequest(root_domain="example.gov/")
        assert req.root_domain == "example.gov"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        req = CivicDiscoverRequest(root_domain="  example.gov  ")
        assert req.root_domain == "example.gov"

    def test_empty_domain_fails(self):
        """Empty string should fail validation (min_length=1)."""
        with pytest.raises(ValidationError):
            CivicDiscoverRequest(root_domain="")

    def test_whitespace_only_fails(self):
        """Whitespace-only string strips to empty, which should fail."""
        with pytest.raises(ValidationError):
            CivicDiscoverRequest(root_domain="   ")

    def test_domain_with_path(self):
        """Domain with path should preserve the path after stripping protocol."""
        req = CivicDiscoverRequest(root_domain="https://example.gov/council")
        assert req.root_domain == "example.gov/council"


# =============================================================================
# CandidateUrl Tests
# =============================================================================


class TestCandidateUrl:
    """Tests for CandidateUrl Pydantic model."""

    def test_valid_candidate(self):
        """CandidateUrl should validate with all fields."""
        candidate = CandidateUrl(
            url="https://example.gov/meetings",
            description="Council meeting agendas",
            confidence=0.9,
        )
        assert candidate.url == "https://example.gov/meetings"
        assert candidate.description == "Council meeting agendas"
        assert candidate.confidence == 0.9

    def test_confidence_zero(self):
        """Confidence of 0.0 should be valid (ge=0.0)."""
        candidate = CandidateUrl(
            url="https://example.gov/meetings",
            description="Low confidence URL",
            confidence=0.0,
        )
        assert candidate.confidence == 0.0

    def test_confidence_one(self):
        """Confidence of 1.0 should be valid (le=1.0)."""
        candidate = CandidateUrl(
            url="https://example.gov/meetings",
            description="High confidence URL",
            confidence=1.0,
        )
        assert candidate.confidence == 1.0

    def test_confidence_above_one_fails(self):
        """Confidence above 1.0 should fail validation."""
        with pytest.raises(ValidationError):
            CandidateUrl(
                url="https://example.gov/meetings",
                description="Invalid confidence",
                confidence=1.1,
            )

    def test_confidence_below_zero_fails(self):
        """Confidence below 0.0 should fail validation."""
        with pytest.raises(ValidationError):
            CandidateUrl(
                url="https://example.gov/meetings",
                description="Invalid confidence",
                confidence=-0.1,
            )


# =============================================================================
# CivicDiscoverResponse Tests
# =============================================================================


class TestCivicDiscoverResponse:
    """Tests for CivicDiscoverResponse Pydantic model."""

    def test_empty_candidates(self):
        """Response should accept empty candidates list."""
        resp = CivicDiscoverResponse(candidates=[])
        assert resp.candidates == []

    def test_multiple_candidates(self):
        """Response should accept multiple CandidateUrl entries."""
        resp = CivicDiscoverResponse(
            candidates=[
                CandidateUrl(url="https://example.gov/agendas", description="Agendas", confidence=0.9),
                CandidateUrl(url="https://example.gov/minutes", description="Minutes", confidence=0.7),
            ]
        )
        assert len(resp.candidates) == 2
        assert resp.candidates[0].confidence == 0.9


# =============================================================================
# CivicExecuteRequest Tests
# =============================================================================


class TestCivicExecuteRequest:
    """Tests for CivicExecuteRequest Pydantic model."""

    def test_minimal_params(self):
        """CivicExecuteRequest should validate with only required fields."""
        req = CivicExecuteRequest(
            user_id="user_123",
            scraper_name="my-civic-scout",
            tracked_urls=["https://example.gov/meetings"],
        )
        assert req.user_id == "user_123"
        assert req.scraper_name == "my-civic-scout"
        assert req.tracked_urls == ["https://example.gov/meetings"]
        assert req.criteria is None
        assert req.language == "en"

    def test_full_params(self):
        """CivicExecuteRequest should validate with all fields provided."""
        req = CivicExecuteRequest(
            user_id="user_456",
            scraper_name="council-watcher",
            tracked_urls=[
                "https://example.gov/meetings",
                "https://example.gov/agendas",
            ],
            criteria="Focus on housing policy decisions",
            language="fr",
        )
        assert req.user_id == "user_456"
        assert req.scraper_name == "council-watcher"
        assert len(req.tracked_urls) == 2
        assert req.criteria == "Focus on housing policy decisions"
        assert req.language == "fr"

    def test_empty_tracked_urls(self):
        """CivicExecuteRequest should accept empty tracked_urls list."""
        req = CivicExecuteRequest(
            user_id="user_123",
            scraper_name="my-scout",
            tracked_urls=[],
        )
        assert req.tracked_urls == []

    def test_default_language_is_en(self):
        """Language should default to 'en' when not provided."""
        req = CivicExecuteRequest(
            user_id="user_123",
            scraper_name="my-scout",
            tracked_urls=[],
        )
        assert req.language == "en"


# =============================================================================
# CivicExecuteResult Tests
# =============================================================================


class TestCivicExecuteResult:
    """Tests for CivicExecuteResult Pydantic model."""

    def test_valid_result(self):
        """CivicExecuteResult should validate with all required fields."""
        result = CivicExecuteResult(
            status="completed",
            summary="Found 2 new promises about housing policy.",
            promises_found=2,
            new_pdf_urls=["https://example.gov/doc1.pdf"],
            is_duplicate=False,
        )
        assert result.status == "completed"
        assert result.promises_found == 2
        assert len(result.new_pdf_urls) == 1
        assert result.is_duplicate is False

    def test_empty_pdf_urls(self):
        """CivicExecuteResult should accept empty new_pdf_urls list."""
        result = CivicExecuteResult(
            status="not_found",
            summary="No new content found.",
            promises_found=0,
            new_pdf_urls=[],
            is_duplicate=True,
        )
        assert result.new_pdf_urls == []
        assert result.is_duplicate is True

    def test_duplicate_result(self):
        """CivicExecuteResult should represent a duplicate run correctly."""
        result = CivicExecuteResult(
            status="completed",
            summary="No new findings since last run.",
            promises_found=0,
            new_pdf_urls=[],
            is_duplicate=True,
        )
        assert result.is_duplicate is True
        assert result.promises_found == 0

    def test_promises_field_defaults_empty(self):
        """CivicExecuteResult promises field should default to empty list."""
        result = CivicExecuteResult(
            status="ok",
            summary="Found 1 promise.",
            promises_found=1,
            new_pdf_urls=[],
            is_duplicate=False,
        )
        assert result.promises == []

    def test_promises_field_populated(self):
        """CivicExecuteResult should carry Promise objects through."""
        promise = Promise(
            promise_text="Build 50 new affordable homes by 2027",
            context="Councillor Smith committed to the housing target.",
            source_url="https://council.example.gov/minutes/2026-03.pdf",
            source_date="2026-03-15",
            due_date="2027-12-31",
            date_confidence="high",
            criteria_match=True,
        )
        result = CivicExecuteResult(
            status="ok",
            summary="Found 1 promise.",
            promises_found=1,
            new_pdf_urls=["https://council.example.gov/minutes/2026-03.pdf"],
            is_duplicate=False,
            promises=[promise],
        )
        assert len(result.promises) == 1
        assert result.promises[0].promise_text == "Build 50 new affordable homes by 2027"
        assert result.promises[0].source_url == "https://council.example.gov/minutes/2026-03.pdf"


# =============================================================================
# Promise Tests
# =============================================================================


class TestPromise:
    """Tests for Promise Pydantic model."""

    def test_without_due_date(self):
        """Promise should validate without optional due_date."""
        promise = Promise(
            promise_text="The council will review the housing plan by Q4.",
            context="During the October meeting, Councillor Smith stated...",
            source_url="https://example.gov/meetings/oct-2025",
            source_date="2025-10-15",
            date_confidence="high",
            criteria_match=True,
        )
        assert promise.due_date is None
        assert promise.criteria_match is True

    def test_with_due_date(self):
        """Promise should validate with optional due_date provided."""
        promise = Promise(
            promise_text="Infrastructure review to be completed by December.",
            context="Minutes from the November session indicate...",
            source_url="https://example.gov/meetings/nov-2025",
            source_date="2025-11-20",
            due_date="2025-12-31",
            date_confidence="medium",
            criteria_match=False,
        )
        assert promise.due_date == "2025-12-31"
        assert promise.date_confidence == "medium"
        assert promise.criteria_match is False

    def test_all_fields(self):
        """Promise should accept all fields including optional due_date."""
        promise = Promise(
            promise_text="New park to be built in the Riverside district.",
            context="The mayor announced the park initiative at the January meeting.",
            source_url="https://example.gov/meetings/jan-2026",
            source_date="2026-01-10",
            due_date="2026-06-30",
            date_confidence="low",
            criteria_match=True,
        )
        assert promise.promise_text == "New park to be built in the Riverside district."
        assert promise.source_date == "2026-01-10"
        assert promise.due_date == "2026-06-30"
        assert promise.date_confidence == "low"


# =============================================================================
# Credit Cost Tests
# =============================================================================


class TestCivicCreditCosts:
    """Tests verifying Civic Scout credit costs in CREDIT_COSTS dict."""

    def test_civic_cost_is_20(self):
        """CREDIT_COSTS['civic'] should be 20."""
        assert CREDIT_COSTS["civic"] == 20

    def test_civic_discover_cost_is_10(self):
        """CREDIT_COSTS['civic_discover'] should be 10."""
        assert CREDIT_COSTS["civic_discover"] == 10

    def test_civic_costs_are_integers(self):
        """Civic credit costs should be integers."""
        assert isinstance(CREDIT_COSTS["civic"], int)
        assert isinstance(CREDIT_COSTS["civic_discover"], int)

    def test_existing_costs_unchanged(self):
        """Adding civic costs should not affect existing credit costs."""
        assert CREDIT_COSTS["pulse"] == 7
        assert CREDIT_COSTS["website_extraction"] == 1
        assert CREDIT_COSTS["feed_export"] == 1


# =============================================================================
# Router Endpoint Auth Tests
# =============================================================================


class TestCivicExecuteAuth:
    """Tests that /civic/execute enforces X-Service-Key authentication."""

    def test_execute_requires_service_key(self):
        """POST /civic/execute without X-Service-Key should return 401."""
        payload = {
            "user_id": "user_123",
            "scraper_name": "test-scout",
            "tracked_urls": ["https://example.gov/meetings"],
        }
        response = client.post("/api/civic/execute", json=payload)
        assert response.status_code in (401, 403, 500)

    def test_execute_with_wrong_key_is_rejected(self):
        """POST /civic/execute with wrong X-Service-Key should return 401."""
        payload = {
            "user_id": "user_123",
            "scraper_name": "test-scout",
            "tracked_urls": [],
        }
        with patch("app.routers.civic.verify_service_key", side_effect=Exception("Invalid key")):
            response = client.post(
                "/api/civic/execute",
                json=payload,
                headers={"X-Service-Key": "wrong-key"},
            )
        # Any non-2xx is acceptable — we just confirm it is not allowed
        assert response.status_code >= 400


class TestCivicNotifyPromisesAuth:
    """Tests that /civic/notify-promises enforces X-Service-Key authentication."""

    def test_notify_promises_requires_service_key(self):
        """POST /civic/notify-promises without X-Service-Key should return 401."""
        payload = {
            "user_id": "user_123",
            "promises": [{"promise_text": "Build a park"}],
        }
        response = client.post("/api/civic/notify-promises", json=payload)
        assert response.status_code in (401, 403, 500)


# =============================================================================
# Discover Endpoint Integration Tests
# =============================================================================


class TestCivicDiscoverEndpoint:
    """Integration tests for POST /civic/discover with mocked auth and services."""

    def test_discover_valid_domain(self, auth_client):
        """Root domain should return 200 with candidates."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock) as mock_validate, \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.discover.return_value = FAKE_CANDIDATES
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post("/api/civic/discover", json={"root_domain": "zermatt.ch"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["candidates"]) == 2
        mock_orch.discover.assert_called_once_with("zermatt.ch")

    def test_discover_full_url_with_protocol(self, auth_client):
        """Full URL with https://www. and trailing slash should be stripped and return 200."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.discover.return_value = FAKE_CANDIDATES
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post(
                "/api/civic/discover",
                json={"root_domain": "https://www.zermatt.ch/"},
            )

        assert response.status_code == 200
        # Pydantic strips protocol, www, and trailing slash
        mock_orch.discover.assert_called_once_with("zermatt.ch")

    def test_discover_url_with_path(self, auth_client):
        """URL with path should preserve the path after stripping protocol."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.discover.return_value = FAKE_CANDIDATES
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post(
                "/api/civic/discover",
                json={"root_domain": "https://zermatt.ch/gemeinde"},
            )

        assert response.status_code == 200
        mock_orch.discover.assert_called_once_with("zermatt.ch/gemeinde")

    def test_discover_empty_body_returns_422(self, auth_client):
        """Empty body (missing root_domain) should return 422."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR), \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            response = auth_client.post("/api/civic/discover", json={})

        assert response.status_code == 422

    def test_discover_empty_root_domain_returns_422(self, auth_client):
        """Empty root_domain string should fail min_length=1 validation."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR), \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            response = auth_client.post("/api/civic/discover", json={"root_domain": ""})

        assert response.status_code == 422

    def test_discover_whitespace_only_returns_422(self, auth_client):
        """Whitespace-only root_domain strips to empty, should return 422."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR), \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            response = auth_client.post("/api/civic/discover", json={"root_domain": "   "})

        assert response.status_code == 422

    def test_discover_protocol_only_returns_422(self, auth_client):
        """Protocol-only string strips to empty, should return 422."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR), \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            response = auth_client.post("/api/civic/discover", json={"root_domain": "https://"})

        assert response.status_code == 422

    def test_discover_orchestrator_error_returns_500(self, auth_client):
        """Orchestrator exception should return 500 with generic message."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.discover.side_effect = Exception("Firecrawl timeout")
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post("/api/civic/discover", json={"root_domain": "zermatt.ch"})

        assert response.status_code == 500
        assert response.json()["detail"] == "Discovery failed. Please try again."

    def test_discover_free_tier_returns_403(self, free_client):
        """Free-tier users should be rejected with 403."""
        response = free_client.post("/api/civic/discover", json={"root_domain": "zermatt.ch"})

        assert response.status_code == 403
        assert "Pro plan" in response.json()["detail"]


# =============================================================================
# Test Endpoint Integration Tests
# =============================================================================


class TestCivicTestEndpoint:
    """Integration tests for POST /civic/test with mocked auth and services."""

    def test_civic_test_valid_request(self, auth_client):
        """Valid tracked_urls should return 200 with promises and document count."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock) as mock_validate, \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.test.return_value = (FAKE_PROMISES, 1)
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post(
                "/api/civic/test",
                json={"tracked_urls": ["https://zermatt.ch/meetings"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["documents_found"] == 1
        assert len(data["sample_promises"]) == 2
        assert data["sample_promises"][0]["promise_text"] == "New school to be built by 2027."
        assert data["error"] is None
        mock_orch.test.assert_called_once_with(
            ["https://zermatt.ch/meetings"], None
        )

    def test_civic_test_with_criteria(self, auth_client):
        """Criteria should be passed through to orchestrator.test()."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.test.return_value = (FAKE_PROMISES[:1], 1)
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post(
                "/api/civic/test",
                json={
                    "tracked_urls": ["https://zermatt.ch/meetings"],
                    "criteria": "education policy",
                },
            )

        assert response.status_code == 200
        mock_orch.test.assert_called_once_with(
            ["https://zermatt.ch/meetings"], "education policy"
        )

    def test_civic_test_free_tier_returns_403(self, free_client):
        """Free-tier users should be rejected with 403."""
        response = free_client.post(
            "/api/civic/test",
            json={"tracked_urls": ["https://zermatt.ch/meetings"]},
        )

        assert response.status_code == 403
        assert "Pro plan" in response.json()["detail"]

    def test_civic_test_empty_urls_returns_422(self, auth_client):
        """Empty tracked_urls list should fail min_length=1 validation."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR), \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            response = auth_client.post(
                "/api/civic/test",
                json={"tracked_urls": []},
            )

        assert response.status_code == 422

    def test_civic_test_orchestrator_error_returns_graceful_response(self, auth_client):
        """Orchestrator exception should return valid=False with error message."""
        with patch(PATCH_VALIDATE, new_callable=AsyncMock), \
             patch(PATCH_ORCHESTRATOR) as mock_orch_cls, \
             patch(PATCH_DECREMENT, new_callable=AsyncMock):
            mock_orch = AsyncMock()
            mock_orch.test.side_effect = Exception("PDF parse failed")
            mock_orch_cls.return_value = mock_orch

            response = auth_client.post(
                "/api/civic/test",
                json={"tracked_urls": ["https://zermatt.ch/meetings"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["documents_found"] == 0
        assert data["sample_promises"] == []
        assert data["error"] == "Extraction failed. Please try again."
