"""
Tests for ScoutService — Web Scout execution pipeline.

Covers:
1. Change tracking format (per-scout tag baseline)
2. Full execute() pipeline (9 steps)
3. Error handling

Run with: python3 -m pytest backend/tests/unit/scouts/test_scout_pipeline.py -v
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.scout_service import ScoutService


@pytest.fixture(autouse=True)
def mock_settings():
    """Ensure settings has required API keys for tests (CI has no .env)."""
    with patch("app.services.scout_service.settings") as mock_s:
        mock_s.openrouter_api_key = "test-key"
        mock_s.llm_model = "test-model"
        mock_s.firecrawl_api_key = "test-key"
        mock_s.environment = "test"
        yield mock_s


# ---------------------------------------------------------------------------
# Helpers: build mock HTTP responses
# ---------------------------------------------------------------------------

def _firecrawl_response(change_status="changed", markdown="# Page\nNew content here", title="Example Page Title"):
    """Build a mock Firecrawl scrape response."""
    resp = MagicMock()
    resp.status_code = 200
    data = {
        "markdown": markdown,
        "changeTracking": {"changeStatus": change_status},
    }
    if title is not None:
        data["metadata"] = {"title": title}
    resp.json.return_value = {
        "success": True,
        "data": data,
    }
    return resp


def _firecrawl_preview_response(markdown="# Page\nPreview content"):
    """Firecrawl response for preview mode (no changeTracking)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "success": True,
        "data": {"markdown": markdown},
    }
    return resp


def _openrouter_response(matches=True, summary="Price dropped to $99", matched_url=None, matched_title=None):
    """Build a mock OpenRouter criteria-analysis response."""
    resp = MagicMock()
    resp.status_code = 200
    payload = {"matches": matches, "summary": summary}
    if matched_url is not None:
        payload["matched_url"] = matched_url
    if matched_title is not None:
        payload["matched_title"] = matched_title
    resp.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps(payload)
            }
        }]
    }
    return resp


def _openrouter_summary_response(summary="This page contains local news articles"):
    """Build a mock OpenRouter plain-text summary response (no JSON wrapper)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": summary}}]
    }
    return resp


def _firecrawl_error_response(status_code=500):
    """Firecrawl returns an HTTP error."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = "Internal Server Error"
    return resp


# ---------------------------------------------------------------------------
# Shared patch targets (patched at import location in scout_service)
# ---------------------------------------------------------------------------

PATCH_HTTP = "app.services.scout_service.get_http_client"
PATCH_NOTIF = "app.services.scout_service.NotificationService"
PATCH_EXEC = "app.services.scout_service.ExecutionDeduplicationService"
PATCH_ATOMIC = "app.services.scout_service.AtomicUnitService"
PATCH_EMAIL = "app.services.scout_service.get_user_email"
PATCH_CREDIT = "app.services.scout_service.decrement_credit"
PATCH_SETTINGS = "app.services.scout_service.settings"


def _build_patches(
    firecrawl_resp=None,
    openrouter_resp=None,
    is_duplicate=False,
    user_email="user@test.com",
):
    """Return a dict of patch kwargs for the common case."""
    if firecrawl_resp is None:
        firecrawl_resp = _firecrawl_response()
    if openrouter_resp is None:
        openrouter_resp = _openrouter_response()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[firecrawl_resp, openrouter_resp])

    mock_exec_instance = AsyncMock()
    mock_exec_instance.check_duplicate = AsyncMock(
        return_value=(is_duplicate, 0.5, [0.1, 0.2])
    )
    mock_exec_instance.store_execution = AsyncMock()

    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_scout_alert = AsyncMock()

    mock_atomic_instance = AsyncMock()
    mock_atomic_instance.process_results = AsyncMock()

    return {
        "mock_client": mock_client,
        "mock_exec_instance": mock_exec_instance,
        "mock_notif_instance": mock_notif_instance,
        "mock_atomic_instance": mock_atomic_instance,
        "user_email": user_email,
    }


def _create_service_with_mocks(mocks):
    """Create a ScoutService with injected mock instances."""
    with patch(PATCH_NOTIF) as MockNotif, \
         patch(PATCH_EXEC) as MockExec, \
         patch(PATCH_ATOMIC) as MockAtomic:
        MockNotif.return_value = mocks["mock_notif_instance"]
        MockExec.return_value = mocks["mock_exec_instance"]
        MockAtomic.return_value = mocks["mock_atomic_instance"]
        service = ScoutService()
    return service


# ===========================================================================
# TestScoutChangeTracking
# ===========================================================================


class TestScoutChangeTracking:
    """Guards the critical per-scout baseline architecture."""

    @pytest.mark.asyncio
    async def test_change_tracking_uses_user_scoped_tag(self):
        """Firecrawl POST body must include changeTracking with user-scoped tag."""
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="my-web-scout",
            )

        # Inspect the first POST call (Firecrawl)
        firecrawl_call = mocks["mock_client"].post.call_args_list[0]
        body = firecrawl_call.kwargs.get("json") or firecrawl_call[1].get("json")

        formats = body["formats"]
        assert "markdown" in formats
        ct_entry = [f for f in formats if isinstance(f, dict) and f.get("type") == "changeTracking"]
        assert len(ct_entry) == 1, "Must have exactly one changeTracking format entry"
        assert ct_entry[0]["tag"] == "user_1#my-web-scout", "tag must be user-scoped"

    @pytest.mark.asyncio
    async def test_different_users_same_name_get_different_tags(self):
        """Two users with identical scout names must get different Firecrawl tags."""
        tags = []
        for uid in ("user_1", "user_2"):
            mocks = _build_patches()
            service = _create_service_with_mocks(mocks)

            with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
                 patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
                 patch(PATCH_CREDIT, new_callable=AsyncMock):
                await service.execute(
                    url="https://example.com",
                    user_id=uid,
                    criteria="price changes",
                    scraper_name="same-name",
                )

            firecrawl_call = mocks["mock_client"].post.call_args_list[0]
            body = firecrawl_call.kwargs.get("json") or firecrawl_call[1].get("json")
            ct_entry = [f for f in body["formats"] if isinstance(f, dict) and f.get("type") == "changeTracking"]
            tags.append(ct_entry[0]["tag"])

        assert tags[0] != tags[1], "Different users must produce different tags"
        assert tags[0] == "user_1#same-name"
        assert tags[1] == "user_2#same-name"

    @pytest.mark.asyncio
    async def test_tag_truncated_at_128_chars(self):
        """Firecrawl tag must not exceed 128 characters."""
        long_name = "x" * 120  # user_id (~6) + "#" (1) + 120 = 127+ chars
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_abcdefghijklmnopqrstuvwxyz",  # 28 chars
                criteria="price changes",
                scraper_name=long_name,
            )

        firecrawl_call = mocks["mock_client"].post.call_args_list[0]
        body = firecrawl_call.kwargs.get("json") or firecrawl_call[1].get("json")
        ct_entry = [f for f in body["formats"] if isinstance(f, dict) and f.get("type") == "changeTracking"]
        assert len(ct_entry[0]["tag"]) <= 128, "Tag must not exceed 128 characters"

    @pytest.mark.asyncio
    async def test_preview_mode_uses_plain_markdown_format(self):
        """Preview mode must use formats: ['markdown'] with no changeTracking."""
        mocks = _build_patches(firecrawl_resp=_firecrawl_preview_response())
        service = _create_service_with_mocks(mocks)

        # 2 HTTP calls: Firecrawl preview + OpenRouter summary (no criteria)
        mocks["mock_client"].post = AsyncMock(side_effect=[
            _firecrawl_preview_response(),
            _openrouter_summary_response(),
        ])

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_1",
                preview_mode=True,
            )

        firecrawl_call = mocks["mock_client"].post.call_args_list[0]
        body = firecrawl_call.kwargs.get("json") or firecrawl_call[1].get("json")

        assert body["formats"] == ["markdown"], "Preview must use plain markdown only"


# ===========================================================================
# TestScoutPipeline
# ===========================================================================


class TestScoutPipeline:
    """Tests the 9-step execute() flow."""

    @pytest.mark.asyncio
    async def test_unchanged_page_returns_early(self):
        """Firecrawl change_status='same' → criteria_status=False, no notification."""
        mocks = _build_patches(firecrawl_resp=_firecrawl_response(change_status="same"))
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
            )

        assert result["scraper_status"] is True
        assert result["criteria_status"] is False
        mocks["mock_notif_instance"].send_scout_alert.assert_not_called()
        # EXEC# record stored for unchanged page
        mocks["mock_exec_instance"].store_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_any_change_mode_generates_summary(self):
        """criteria=None (Any Change) + change detected → LLM summary generated."""
        firecrawl_resp = _firecrawl_response(change_status="changed")
        summary_resp = _openrouter_summary_response("Local council approved new zoning laws")
        mocks = _build_patches(firecrawl_resp=firecrawl_resp)
        service = _create_service_with_mocks(mocks)

        # 2 HTTP calls: Firecrawl + OpenRouter summary
        mocks["mock_client"].post = AsyncMock(side_effect=[firecrawl_resp, summary_resp])

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria=None,  # Any Change mode
                scraper_name="scout-1",
            )

        assert result["criteria_status"] is True
        assert result["summary"] == "Local council approved new zoning laws"
        # 2 POSTs: Firecrawl + OpenRouter summary
        assert mocks["mock_client"].post.call_count == 2

    @pytest.mark.asyncio
    async def test_criteria_match_sends_notification(self):
        """Change detected + LLM match → send_scout_alert called."""
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value="user@test.com"), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
            )

        assert result["criteria_status"] is True
        mocks["mock_notif_instance"].send_scout_alert.assert_called_once()
        call_kwargs = mocks["mock_notif_instance"].send_scout_alert.call_args.kwargs
        assert call_kwargs["to_email"] == "user@test.com"
        assert call_kwargs["scout_name"] == "scout-1"

    @pytest.mark.asyncio
    async def test_criteria_no_match_skips_notification(self):
        """LLM returns matches=False → no notification, EXEC# stored."""
        mocks = _build_patches(openrouter_resp=_openrouter_response(matches=False))
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
            )

        assert result["criteria_status"] is False
        mocks["mock_notif_instance"].send_scout_alert.assert_not_called()
        mocks["mock_exec_instance"].store_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_detection_prevents_notification(self):
        """check_duplicate returns True → no notification, is_duplicate=True in EXEC#."""
        mocks = _build_patches(is_duplicate=True)
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
            )

        assert result["criteria_status"] is False
        mocks["mock_notif_instance"].send_scout_alert.assert_not_called()
        # Verify EXEC# stored with is_duplicate=True
        store_call = mocks["mock_exec_instance"].store_execution.call_args
        assert store_call.kwargs["is_duplicate"] is True

    @pytest.mark.asyncio
    async def test_preview_mode_no_side_effects(self):
        """Preview mode: no EXEC# storage, no notification, no credit charge."""
        mocks = _build_patches(firecrawl_resp=_firecrawl_preview_response())
        service = _create_service_with_mocks(mocks)

        mocks["mock_client"].post = AsyncMock(side_effect=[
            _firecrawl_preview_response(),
            _openrouter_summary_response(),
        ])

        mock_credit = AsyncMock()
        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new=mock_credit):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                preview_mode=True,
                skip_notification=True,
                skip_credit_charge=True,
            )

        assert result["scraper_status"] is True
        assert result["summary"] != "Page content updated"
        mocks["mock_exec_instance"].store_execution.assert_not_called()
        mocks["mock_notif_instance"].send_scout_alert.assert_not_called()
        mock_credit.assert_not_called()

    @pytest.mark.asyncio
    async def test_credit_charged_only_on_match(self):
        """decrement_credit called only when criteria matched (not on no-match)."""
        # Case 1: match → credit charged
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)
        mock_credit = AsyncMock()

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new=mock_credit):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price",
                scraper_name="scout-1",
            )

        assert result["criteria_status"] is True
        mock_credit.assert_called_once_with(
            "user_1", org_id=None,
            operation="website_extraction", scout_name="scout-1", scout_type="web",
        )

        # Case 2: no match → skip_credit_charge not relevant, but criteria_status False
        # means the function returns before Step 8
        mocks2 = _build_patches(openrouter_resp=_openrouter_response(matches=False))
        service2 = _create_service_with_mocks(mocks2)
        mock_credit2 = AsyncMock()

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks2["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks2["user_email"]), \
             patch(PATCH_CREDIT, new=mock_credit2):
            result2 = await service2.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price",
                scraper_name="scout-1",
            )

        assert result2["criteria_status"] is False
        mock_credit2.assert_not_called()

    @pytest.mark.asyncio
    async def test_any_change_summarize_fallback_on_llm_failure(self):
        """OpenRouter returns error for summary → falls back to page title, NOT scraper_status=False."""
        firecrawl_resp = _firecrawl_response(change_status="changed", title="City Council Meeting Notes")
        openrouter_error = MagicMock()
        openrouter_error.status_code = 500
        openrouter_error.text = "Internal Server Error"

        mocks = _build_patches(firecrawl_resp=firecrawl_resp)
        service = _create_service_with_mocks(mocks)

        mocks["mock_client"].post = AsyncMock(side_effect=[firecrawl_resp, openrouter_error])

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria=None,
                scraper_name="scout-1",
            )

        # Scrape succeeded — scraper_status must be True
        assert result["scraper_status"] is True
        assert result["criteria_status"] is True
        # Falls back to page title
        assert result["summary"] == "City Council Meeting Notes"

    @pytest.mark.asyncio
    async def test_any_change_empty_markdown_uses_title(self):
        """Firecrawl returns empty markdown → uses page_title directly without calling LLM."""
        firecrawl_resp = _firecrawl_response(
            change_status="changed", markdown="", title="Breaking News Page"
        )
        mocks = _build_patches(firecrawl_resp=firecrawl_resp)
        service = _create_service_with_mocks(mocks)

        # Only 1 HTTP call (Firecrawl) — no OpenRouter since markdown is empty
        mocks["mock_client"].post = AsyncMock(return_value=firecrawl_resp)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria=None,
                scraper_name="scout-1",
            )

        assert result["scraper_status"] is True
        assert result["criteria_status"] is True
        assert result["summary"] == "Breaking News Page"
        # Only 1 POST (Firecrawl) — LLM not called for empty markdown
        assert mocks["mock_client"].post.call_count == 1

    @pytest.mark.asyncio
    async def test_matched_url_and_title_passed_to_notification(self):
        """When LLM returns matched_url and matched_title, they are passed to send_scout_alert."""
        mocks = _build_patches(
            openrouter_resp=_openrouter_response(
                matches=True,
                summary="New article about ICE enforcement",
                matched_url="https://www.politico.com/news/ice-article",
                matched_title="California bill would block immigration agents",
            )
        )
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value="user@test.com"), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://www.politico.com/",
                user_id="user_1",
                criteria="ICE",
                scraper_name="ice-monitor",
            )

        mocks["mock_notif_instance"].send_scout_alert.assert_called_once()
        call_kwargs = mocks["mock_notif_instance"].send_scout_alert.call_args.kwargs
        assert call_kwargs["matched_url"] == "https://www.politico.com/news/ice-article"
        assert call_kwargs["matched_title"] == "California bill would block immigration agents"

    @pytest.mark.asyncio
    async def test_no_matched_url_passes_empty_to_notification(self):
        """When LLM omits matched_url, empty strings are passed to send_scout_alert."""
        mocks = _build_patches(
            openrouter_resp=_openrouter_response(matches=True, summary="Price dropped to $99")
        )
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value="user@test.com"), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
            )

        call_kwargs = mocks["mock_notif_instance"].send_scout_alert.call_args.kwargs
        assert call_kwargs["matched_url"] == ""
        assert call_kwargs["matched_title"] == ""

    @pytest.mark.asyncio
    async def test_any_change_mode_passes_empty_matched_fields(self):
        """Any Change mode (no criteria) passes empty matched_url/matched_title."""
        firecrawl_resp = _firecrawl_response(change_status="changed")
        summary_resp = _openrouter_summary_response("Local council approved new zoning laws")
        mocks = _build_patches(firecrawl_resp=firecrawl_resp)
        service = _create_service_with_mocks(mocks)

        mocks["mock_client"].post = AsyncMock(side_effect=[firecrawl_resp, summary_resp])

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value="user@test.com"), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria=None,
                scraper_name="scout-1",
            )

        call_kwargs = mocks["mock_notif_instance"].send_scout_alert.call_args.kwargs
        assert call_kwargs["matched_url"] == ""
        assert call_kwargs["matched_title"] == ""


# ===========================================================================
# TestScoutErrorHandling
# ===========================================================================


class TestScoutErrorHandling:
    """Tests error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_firecrawl_failure_returns_scraper_status_false(self):
        """HTTP 500 from Firecrawl → scraper_status=False."""
        mocks = _build_patches(firecrawl_resp=_firecrawl_error_response(500))
        service = _create_service_with_mocks(mocks)

        mocks["mock_client"].post = AsyncMock(return_value=_firecrawl_error_response(500))

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="test",
                scraper_name="scout-1",
            )

        assert result["scraper_status"] is False
        assert result["criteria_status"] is False

    @pytest.mark.asyncio
    async def test_notification_failure_doesnt_crash(self):
        """send_scout_alert raises → execute still returns success."""
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)
        mocks["mock_notif_instance"].send_scout_alert = AsyncMock(
            side_effect=Exception("SMTP error")
        )

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price",
                scraper_name="scout-1",
            )

        # Still returns success — notification failure is non-critical
        assert result["scraper_status"] is True
        assert result["criteria_status"] is True


# ===========================================================================
# TestUnitExtraction — Regression guards for page scout unit extraction
# ===========================================================================


class TestUnitExtraction:
    """Guards against accidental removal of page scout unit extraction (commit 5fa76cd regression)."""

    @pytest.mark.asyncio
    async def test_unit_extraction_called_on_criteria_match_with_location(self):
        """process_results must be called when location is provided and criteria match."""
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
                location={"displayName": "Zurich", "city": "Zurich", "state": "ZH", "country": "CH"},
            )

        assert result["criteria_status"] is True
        mocks["mock_atomic_instance"].process_results.assert_called_once()
        call_kwargs = mocks["mock_atomic_instance"].process_results.call_args.kwargs
        assert call_kwargs["scout_type"] == "web"
        assert call_kwargs["user_id"] == "user_1"

    @pytest.mark.asyncio
    async def test_unit_extraction_called_with_topic_only(self):
        """process_results must be called when topic is provided (no location)."""
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
                topic="technology",
            )

        assert result["criteria_status"] is True
        mocks["mock_atomic_instance"].process_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_unit_extraction_skipped_in_preview_mode(self):
        """process_results must NOT be called in preview mode."""
        mocks = _build_patches(firecrawl_resp=_firecrawl_preview_response())
        service = _create_service_with_mocks(mocks)

        mocks["mock_client"].post = AsyncMock(side_effect=[
            _firecrawl_preview_response(),
            _openrouter_summary_response(),
        ])

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_1",
                preview_mode=True,
                skip_notification=True,
                skip_credit_charge=True,
                location={"displayName": "Zurich", "city": "Zurich", "state": "ZH", "country": "CH"},
            )

        mocks["mock_atomic_instance"].process_results.assert_not_called()

    @pytest.mark.asyncio
    async def test_unit_extraction_skipped_without_location_or_topic(self):
        """process_results must NOT be called when neither location nor topic is provided."""
        mocks = _build_patches()
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
            )

        mocks["mock_atomic_instance"].process_results.assert_not_called()

    @pytest.mark.asyncio
    async def test_unit_extraction_failure_does_not_crash(self):
        """process_results failure must not affect notification or result."""
        mocks = _build_patches()
        mocks["mock_atomic_instance"].process_results = AsyncMock(
            side_effect=Exception("DynamoDB error")
        )
        service = _create_service_with_mocks(mocks)

        with patch(PATCH_HTTP, new_callable=AsyncMock, return_value=mocks["mock_client"]), \
             patch(PATCH_EMAIL, new_callable=AsyncMock, return_value=mocks["user_email"]), \
             patch(PATCH_CREDIT, new_callable=AsyncMock):
            result = await service.execute(
                url="https://example.com",
                user_id="user_1",
                criteria="price changes",
                scraper_name="scout-1",
                location={"displayName": "Zurich", "city": "Zurich", "state": "ZH", "country": "CH"},
            )

        assert result["criteria_status"] is True
        assert result["scraper_status"] is True
        mocks["mock_notif_instance"].send_scout_alert.assert_called_once()


# ===========================================================================
# TestDateValueValidation — date regex validation
# ===========================================================================


class TestDateValueValidation:
    """Tests _DATE_RE validation in atomic_unit_service."""

    def test_valid_date_passes(self):
        from app.services.atomic_unit_service import _DATE_RE
        assert _DATE_RE.match("2025-01-10")

    def test_invalid_text_date_rejected(self):
        from app.services.atomic_unit_service import _DATE_RE
        assert not _DATE_RE.match("March 2025")

    def test_relative_date_rejected(self):
        from app.services.atomic_unit_service import _DATE_RE
        assert not _DATE_RE.match("next Monday")

    def test_none_handled(self):
        """None date should not reach regex — guard at call site."""
        from app.services.atomic_unit_service import _DATE_RE
        raw_date = None
        result = raw_date if raw_date and _DATE_RE.match(raw_date) else None
        assert result is None

    def test_partial_date_rejected(self):
        from app.services.atomic_unit_service import _DATE_RE
        assert not _DATE_RE.match("2025-01")
