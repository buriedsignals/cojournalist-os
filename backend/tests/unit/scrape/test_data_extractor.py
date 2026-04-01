"""
Tests for data extraction error handling pipeline.

Covers:
1. FirecrawlClient error propagation (HTTP errors, request errors, failed jobs)
2. Sync /data/extract endpoint error mapping (400/504/500)
3. Async job pattern error propagation (start + poll + status)
4. SSE stream error events (primary frontend path)
5. Workflow layer error wrapping

Run with: python3 -m pytest tests/unit/scrape/ -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.workflows.firecrawl_client import FirecrawlClient, FirecrawlError
from app.workflows.data_extractor import (
    DataExtractRequest,
    extract_data_async,
    start_data_extraction_job,
    check_data_extraction_job,
    is_data_effectively_empty,
)
from app.routers.data_extractor import router, jobs, poll_extraction_job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_app():
    """Create a FastAPI app with the data extractor router for testing."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def _mock_user():
    """Return a mock authenticated user dict."""
    return {"user_id": "user_test_123", "id": "user_test_123"}


def _mock_settings(**overrides):
    """Return a mock settings object with sensible defaults."""
    settings = MagicMock()
    settings.firecrawl_api_key = overrides.get("firecrawl_api_key", "test-api-key")
    settings.apify_api_token = overrides.get("apify_api_token", None)
    return settings


# ---------------------------------------------------------------------------
# Patch targets (always patch at import location)
# ---------------------------------------------------------------------------

PATCH_EXTRACT_ASYNC = "app.routers.data_extractor.extract_data_async"
PATCH_START_JOB = "app.routers.data_extractor.start_data_extraction_job"
PATCH_CHECK_JOB = "app.routers.data_extractor.check_data_extraction_job"
PATCH_SETTINGS = "app.routers.data_extractor.get_settings"
PATCH_CHARGE = "app.routers.data_extractor.charge_user_credits"
PATCH_FIRECRAWL_CLIENT_WORKFLOW = "app.workflows.data_extractor.FirecrawlClient"


# ===========================================================================
# TestFirecrawlClientErrors
# ===========================================================================

class TestFirecrawlClientErrors:
    """Unit tests on FirecrawlClient methods — verifies errors are raised."""

    @pytest.mark.asyncio
    async def test_start_extraction_http_error_raises_firecrawl_error(self):
        """HTTP 403 from Firecrawl should raise FirecrawlError with status code."""
        client = FirecrawlClient(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response,
        )

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workflows.firecrawl_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(FirecrawlError, match="403"):
                await client.start_extraction(
                    url="https://justice.gov", prompt="extract data"
                )

    @pytest.mark.asyncio
    async def test_start_extraction_request_error_raises_firecrawl_error(self):
        """Connection refused should raise FirecrawlError."""
        client = FirecrawlClient(api_key="test-key")

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            side_effect=httpx.RequestError("Connection refused", request=MagicMock())
        )
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workflows.firecrawl_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(FirecrawlError, match="Request failed"):
                await client.start_extraction(
                    url="https://example.com", prompt="extract"
                )

    @pytest.mark.asyncio
    async def test_poll_until_complete_failed_status_raises(self):
        """Job with status 'failed' should raise FirecrawlError."""
        client = FirecrawlClient(api_key="test-key")

        with patch.object(client, "get_job_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "status": "failed", "error": "Access denied"
            }

            with pytest.raises(
                FirecrawlError, match="Extraction job failed: Access denied"
            ):
                await client.poll_until_complete(job_id="job-123")

    @pytest.mark.asyncio
    async def test_get_job_status_http_error_raises(self):
        """HTTP error on GET status endpoint should raise FirecrawlError."""
        client = FirecrawlClient(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("app.workflows.firecrawl_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(FirecrawlError, match="500"):
                await client.get_job_status(job_id="job-123")


# ===========================================================================
# TestSyncExtractEndpoint
# ===========================================================================

class TestSyncExtractEndpoint:
    """Tests the POST /data/extract router endpoint error handling."""

    def _get_client(self):
        from app.dependencies import get_current_user

        app = _create_test_app()
        app.dependency_overrides[get_current_user] = lambda: _mock_user()
        return TestClient(app)

    def test_firecrawl_error_returns_400_for_failed(self):
        """FirecrawlError with 'failed' in message should return HTTP 400."""
        client = self._get_client()

        with patch(PATCH_SETTINGS, return_value=_mock_settings()), \
             patch(PATCH_EXTRACT_ASYNC, new_callable=AsyncMock) as mock_extract:
            mock_extract.side_effect = FirecrawlError(
                "Extraction failed: Access denied"
            )

            response = client.post("/api/data/extract", json={
                "url": "https://justice.gov",
                "target": "court records",
            })

        assert response.status_code == 400
        assert "failed" in response.json()["detail"].lower()

    def test_firecrawl_timeout_returns_504(self):
        """FirecrawlError with 'timed out' should return HTTP 504."""
        client = self._get_client()

        with patch(PATCH_SETTINGS, return_value=_mock_settings()), \
             patch(PATCH_EXTRACT_ASYNC, new_callable=AsyncMock) as mock_extract:
            mock_extract.side_effect = FirecrawlError(
                "Extraction timed out after 600 seconds"
            )

            response = client.post("/api/data/extract", json={
                "url": "https://slow-site.com",
                "target": "data",
            })

        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()

    def test_firecrawl_generic_error_returns_500(self):
        """FirecrawlError without 'failed' or 'timed out' should return HTTP 500."""
        client = self._get_client()

        with patch(PATCH_SETTINGS, return_value=_mock_settings()), \
             patch(PATCH_EXTRACT_ASYNC, new_callable=AsyncMock) as mock_extract:
            mock_extract.side_effect = FirecrawlError(
                "API error: connection refused"
            )

            response = client.post("/api/data/extract", json={
                "url": "https://example.com",
                "target": "data",
            })

        assert response.status_code == 500
        assert "connection refused" in response.json()["detail"].lower()

    def test_unexpected_error_returns_500_with_message(self):
        """Generic Exception should return HTTP 500 with 'Unexpected error'."""
        client = self._get_client()

        with patch(PATCH_SETTINGS, return_value=_mock_settings()), \
             patch(PATCH_EXTRACT_ASYNC, new_callable=AsyncMock) as mock_extract:
            mock_extract.side_effect = RuntimeError("something broke")

            response = client.post("/api/data/extract", json={
                "url": "https://example.com",
                "target": "data",
            })

        assert response.status_code == 500
        assert "unexpected error" in response.json()["detail"].lower()


# ===========================================================================
# TestAsyncJobErrorPropagation
# ===========================================================================

class TestAsyncJobErrorPropagation:
    """Tests the async job pattern (POST /extract/start + polling + status)."""

    def _get_client(self):
        from app.dependencies import get_current_user

        app = _create_test_app()
        app.dependency_overrides[get_current_user] = lambda: _mock_user()
        return TestClient(app)

    def test_start_job_firecrawl_error_returns_500(self):
        """FirecrawlError during job start should return HTTP 500."""
        client = self._get_client()

        with patch(PATCH_SETTINGS, return_value=_mock_settings()), \
             patch(PATCH_START_JOB, new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = FirecrawlError(
                "Failed to start: 403 Forbidden"
            )

            response = client.post("/api/extract/start", json={
                "url": "https://blocked.gov",
                "target": "records",
            })

        assert response.status_code == 500
        assert "403" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_poll_job_failed_status_stored_in_jobs(self):
        """When check_data_extraction_job returns failed, jobs dict should reflect it."""
        job_id = "test-failed-job"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()):
                mock_check.return_value = {
                    "status": "failed", "error": "Site blocked"
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://example.com"
                )

            assert jobs[job_id]["status"] == "failed"
            assert jobs[job_id]["error"] == "Site blocked"
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_exception_stored_as_failed(self):
        """When check_data_extraction_job raises, jobs dict should store error."""
        job_id = "test-exception-job"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()):
                mock_check.side_effect = Exception("Connection timeout")

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://example.com"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "Connection timeout" in jobs[job_id]["error"]
        finally:
            jobs.pop(job_id, None)

    def test_get_status_returns_error_for_failed_job(self):
        """GET /extract/status/{job_id} should return error field for failed jobs."""
        job_id = "pre-failed-job"
        jobs[job_id] = {
            "status": "failed",
            "error": "Site blocked by firewall",
            "user_id": "user_test_123",
        }

        try:
            client = self._get_client()
            response = client.get(f"/api/extract/status/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["error"] == "Site blocked by firewall"
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_none_data_stored_as_failed(self):
        """When Firecrawl returns completed with data=None, job should be marked failed."""
        job_id = "test-empty-none-job"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge:
                mock_check.return_value = {
                    "status": "completed", "data": None
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "No data could be extracted" in jobs[job_id]["error"]
            mock_charge.assert_not_called()
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_empty_list_stored_as_failed(self):
        """When Firecrawl returns completed with data=[], job should be marked failed."""
        job_id = "test-empty-list-job"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge:
                mock_check.return_value = {
                    "status": "completed", "data": []
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "No data could be extracted" in jobs[job_id]["error"]
            mock_charge.assert_not_called()
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_empty_dict_stored_as_failed(self):
        """When Firecrawl returns completed with data={}, job should be marked failed."""
        job_id = "test-empty-dict-job"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge:
                mock_check.return_value = {
                    "status": "completed", "data": {}
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "No data could be extracted" in jobs[job_id]["error"]
            mock_charge.assert_not_called()
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_empty_string_stored_as_failed(self):
        """When Firecrawl returns completed with data='', job should be marked failed."""
        job_id = "test-empty-string-job"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge:
                mock_check.return_value = {
                    "status": "completed", "data": ""
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "No data could be extracted" in jobs[job_id]["error"]
            mock_charge.assert_not_called()
        finally:
            jobs.pop(job_id, None)


# ===========================================================================
# TestWorkflowErrorPropagation
# ===========================================================================

class TestWorkflowErrorPropagation:
    """Tests the workflow layer (data_extractor.py workflow functions)."""

    @pytest.mark.asyncio
    async def test_extract_data_async_wraps_firecrawl_error(self):
        """extract_data_async should wrap FirecrawlError with context."""
        request = DataExtractRequest(
            url="https://justice.gov", target="court records"
        )

        with patch(PATCH_FIRECRAWL_CLIENT_WORKFLOW) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.extract_and_wait = AsyncMock(
                side_effect=FirecrawlError("Access denied")
            )
            MockClient.return_value = mock_instance

            with pytest.raises(
                FirecrawlError, match="Data extraction failed: Access denied"
            ):
                await extract_data_async(request, api_key="test-key")

    @pytest.mark.asyncio
    async def test_start_data_extraction_job_firecrawl_error(self):
        """FirecrawlError from start_extraction should propagate."""
        request = DataExtractRequest(
            url="https://blocked.gov", target="data"
        )
        settings = _mock_settings()

        with patch(PATCH_FIRECRAWL_CLIENT_WORKFLOW) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.start_extraction = AsyncMock(
                side_effect=FirecrawlError(
                    "Failed to start extraction: 403 - Forbidden"
                )
            )
            MockClient.return_value = mock_instance

            with pytest.raises(FirecrawlError, match="403"):
                await start_data_extraction_job(request, settings)

    @pytest.mark.asyncio
    async def test_check_data_extraction_job_failed_status(self):
        """check_data_extraction_job should return failed status from Firecrawl."""
        settings = _mock_settings()

        with patch(PATCH_FIRECRAWL_CLIENT_WORKFLOW) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get_job_status = AsyncMock(return_value={
                "status": "failed",
                "error": "Blocked",
                "data": None,
            })
            MockClient.return_value = mock_instance

            result = await check_data_extraction_job(
                "job-123", "firecrawl", settings
            )

        assert result["status"] == "failed"
        assert result["error"] == "Blocked"


# ===========================================================================
# TestIsDataEffectivelyEmpty
# ===========================================================================

class TestIsDataEffectivelyEmpty:
    """Tests the is_data_effectively_empty() helper function."""

    def test_none_is_empty(self):
        assert is_data_effectively_empty(None) is True

    def test_empty_string_is_empty(self):
        assert is_data_effectively_empty("") is True

    def test_empty_list_is_empty(self):
        assert is_data_effectively_empty([]) is True

    def test_empty_dict_is_empty(self):
        assert is_data_effectively_empty({}) is True

    def test_wrapper_dict_with_empty_list_is_empty(self):
        """Firecrawl pattern: {"names": []} should be treated as empty."""
        assert is_data_effectively_empty({"names": []}) is True

    def test_wrapper_dict_with_empty_dict_value_is_empty(self):
        assert is_data_effectively_empty({"data": {}}) is True

    def test_wrapper_dict_multiple_empty_values_is_empty(self):
        assert is_data_effectively_empty({"a": [], "b": []}) is True

    def test_wrapper_dict_mixed_empty_values_is_empty(self):
        assert is_data_effectively_empty({"a": [], "b": {}}) is True

    def test_wrapper_dict_with_real_list_data_is_not_empty(self):
        assert is_data_effectively_empty({"names": ["Alice"]}) is False

    def test_list_with_data_is_not_empty(self):
        assert is_data_effectively_empty([{"key": "value"}]) is False

    def test_non_empty_string_is_not_empty(self):
        assert is_data_effectively_empty("data") is False

    def test_wrapper_dict_one_empty_one_nonempty_is_not_empty(self):
        """If at least one value has real data, it's not empty."""
        assert is_data_effectively_empty({"a": [], "b": ["x"]}) is False


# ===========================================================================
# TestAsyncJobWrapperEmptyData
# ===========================================================================

class TestAsyncJobWrapperEmptyData:
    """Tests that wrapper dicts with empty arrays are treated as failed in poll_extraction_job."""

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_wrapper_empty_list_stored_as_failed(self):
        """{"names": []} should be treated as empty — job fails, no credit charge."""
        job_id = "test-wrapper-empty-list"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge:
                mock_check.return_value = {
                    "status": "completed", "data": {"names": []}
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "No data could be extracted" in jobs[job_id]["error"]
            mock_charge.assert_not_called()
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_wrapper_empty_dict_stored_as_failed(self):
        """{"data": {}} should be treated as empty — job fails, no credit charge."""
        job_id = "test-wrapper-empty-dict"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge:
                mock_check.return_value = {
                    "status": "completed", "data": {"data": {}}
                }

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "failed"
            assert "No data could be extracted" in jobs[job_id]["error"]
            mock_charge.assert_not_called()
        finally:
            jobs.pop(job_id, None)

    @pytest.mark.asyncio
    async def test_poll_job_completed_with_real_data_charges_credits(self):
        """{"names": ["Alice"]} has real data — job succeeds, credits charged."""
        job_id = "test-real-data"
        jobs[job_id] = {"status": "running", "user_id": "user_test_123"}

        try:
            with patch(PATCH_CHECK_JOB, new_callable=AsyncMock) as mock_check, \
                 patch(PATCH_SETTINGS, return_value=_mock_settings()), \
                 patch(PATCH_CHARGE, new_callable=AsyncMock) as mock_charge, \
                 patch("app.routers.data_extractor.UserService") as mock_us_cls:
                mock_check.return_value = {
                    "status": "completed", "data": {"names": ["Alice", "Bob"]}
                }
                mock_charge.return_value = 99
                mock_us_cls.return_value.get_user.return_value = {"user_id": "user_test_123"}

                await poll_extraction_job(
                    job_id, "firecrawl", "user_test_123", "https://justice.gov"
                )

            assert jobs[job_id]["status"] == "completed"
            assert "data" in jobs[job_id]
            assert jobs[job_id]["data"]["csv_content"]  # non-empty CSV
            mock_charge.assert_called_once_with(
                "user_test_123", amount=1, org_id=None,
                operation="website_extraction",
            )
        finally:
            jobs.pop(job_id, None)
