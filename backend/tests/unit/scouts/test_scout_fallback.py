"""Tests for plain scrape fallback in Page Scout pipeline."""
import hashlib
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.scout_service import ScoutService


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestFallbackTrigger:
    """Verify plain scrape fallback is called only when changeTracking fails."""

    @pytest.fixture
    def service(self):
        svc = ScoutService()
        svc.exec_dedup_service = MagicMock()
        svc.exec_dedup_service.store_execution = AsyncMock()
        svc.exec_dedup_service.check_duplicate = AsyncMock(return_value=(False, 0.0, None))
        svc.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=None)
        svc.notification_service = MagicMock()
        svc.notification_service.send_scout_alert = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_firecrawl_success_no_fallback(self, service):
        """When Firecrawl changeTracking succeeds, _firecrawl_scrape is called only once (with tag)."""
        firecrawl_result = {
            "markdown": "# Page\n\nContent",
            "metadata": {"title": "Page"},
            "changeTracking": {"changeStatus": "new"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, return_value=firecrawl_result) as mock_scrape, \
             patch.object(service, "_summarize_page", new_callable=AsyncMock, return_value="Summary"), \
             patch("app.services.scout_service.get_user_email", new_callable=AsyncMock, return_value="test@test.com"), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")
            mock_scrape.assert_called_once()

    @pytest.mark.asyncio
    async def test_firecrawl_fails_triggers_fallback(self, service):
        """When changeTracking returns None, _firecrawl_scrape is called twice (with tag, then without)."""
        fallback_result = {
            "markdown": "# Fallback Content",
            "metadata": {"title": "Fallback Content"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, fallback_result]) as mock_scrape, \
             patch.object(service, "_summarize_page", new_callable=AsyncMock, return_value="Summary"), \
             patch("app.services.scout_service.get_user_email", new_callable=AsyncMock, return_value="test@test.com"), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            result = await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")
            assert mock_scrape.call_count == 2
            # Second call should be without tag (plain scrape fallback)
            second_call_args, second_call_kwargs = mock_scrape.call_args_list[1]
            assert second_call_args == ("https://example.com",)
            assert "tag" not in second_call_kwargs
            assert result["scraper_status"] is True

    @pytest.mark.asyncio
    async def test_both_fail_returns_error(self, service):
        """When both changeTracking and plain scrape fail, returns scraper_status=False."""
        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, None]):

            result = await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")
            assert result["scraper_status"] is False

    @pytest.mark.asyncio
    async def test_preview_mode_no_fallback(self, service):
        """Preview mode calls _firecrawl_scrape without tag. Returns error when it fails."""
        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, return_value=None):

            result = await service.execute(
                url="https://example.com", user_id="user1",
                scraper_name="scout1", preview_mode=True
            )
            assert result["scraper_status"] is False


class TestHashChangeDetection:
    """Verify hash-based change detection for plain scrape fallback path."""

    @pytest.fixture
    def service(self):
        svc = ScoutService()
        svc.exec_dedup_service = MagicMock()
        svc.exec_dedup_service.store_execution = AsyncMock()
        svc.exec_dedup_service.check_duplicate = AsyncMock(return_value=(False, 0.0, None))
        svc.notification_service = MagicMock()
        svc.notification_service.send_scout_alert = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_no_previous_hash_returns_new(self, service):
        """First plain scrape run: no previous hash -> change_status='new'."""
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=None)

        fallback_result = {
            "markdown": "# Content\n\nNew page",
            "metadata": {"title": "Content"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, fallback_result]), \
             patch.object(service, "_summarize_page", new_callable=AsyncMock, return_value="Summary"), \
             patch("app.services.scout_service.get_user_email", new_callable=AsyncMock, return_value="test@test.com"), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            result = await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")
            assert result["scraper_status"] is True
            assert result["criteria_status"] is True

    @pytest.mark.asyncio
    async def test_same_hash_returns_same(self, service):
        """Same hash as previous -> change_status='same', early return."""
        markdown = "# Content\n\nSame page"
        stored_hash = _sha256(markdown)
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=stored_hash)

        fallback_result = {
            "markdown": markdown,
            "metadata": {"title": "Content"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, fallback_result]), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            result = await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")
            assert result["scraper_status"] is True
            assert result["criteria_status"] is False

    @pytest.mark.asyncio
    async def test_different_hash_returns_changed(self, service):
        """Different hash -> change_status='changed'."""
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value="old_hash_value")

        fallback_result = {
            "markdown": "# Updated Content\n\nNew stuff here",
            "metadata": {"title": "Updated Content"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, fallback_result]), \
             patch.object(service, "_summarize_page", new_callable=AsyncMock, return_value="Content updated"), \
             patch("app.services.scout_service.get_user_email", new_callable=AsyncMock, return_value="test@test.com"), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            result = await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")
            assert result["scraper_status"] is True
            assert result["criteria_status"] is True

    @pytest.mark.asyncio
    async def test_content_hash_stored_on_exec_record(self, service):
        """content_hash is passed to store_execution when using plain scrape fallback."""
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=None)

        markdown = "# Page\n\nContent"
        expected_hash = _sha256(markdown)
        fallback_result = {
            "markdown": markdown,
            "metadata": {"title": "Page"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, fallback_result]), \
             patch.object(service, "_summarize_page", new_callable=AsyncMock, return_value="Summary"), \
             patch("app.services.scout_service.get_user_email", new_callable=AsyncMock, return_value="test@test.com"), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")

        store_calls = service.exec_dedup_service.store_execution.call_args_list
        match_call = [c for c in store_calls if c[1].get("content_hash")]
        assert len(match_call) >= 1
        assert match_call[-1][1]["content_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_provider_stored_as_firecrawl_plain(self, service):
        """provider='firecrawl_plain' is stored on EXEC# when fallback used."""
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=None)

        fallback_result = {
            "markdown": "# Page\n\nContent",
            "metadata": {"title": "Page"},
        }

        with patch.object(service, "_firecrawl_scrape", new_callable=AsyncMock, side_effect=[None, fallback_result]), \
             patch.object(service, "_summarize_page", new_callable=AsyncMock, return_value="Summary"), \
             patch("app.services.scout_service.get_user_email", new_callable=AsyncMock, return_value="test@test.com"), \
             patch("app.services.scout_service.decrement_credit", new_callable=AsyncMock):

            await service.execute(url="https://example.com", user_id="user1", scraper_name="scout1")

        store_calls = service.exec_dedup_service.store_execution.call_args_list
        provider_calls = [c for c in store_calls if c[1].get("provider") == "firecrawl_plain"]
        assert len(provider_calls) >= 1


class TestDetectChangeByHash:
    """Unit tests for the _detect_change_by_hash helper method."""

    @pytest.fixture
    def service(self):
        svc = ScoutService()
        svc.exec_dedup_service = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_no_previous_hash_returns_new(self, service):
        """No previous hash stored -> returns ('new', hash)."""
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=None)
        text = "Hello world"
        status, content_hash = await service._detect_change_by_hash(text, "user1", "scout1")
        assert status == "new"
        assert content_hash == _sha256(text)

    @pytest.mark.asyncio
    async def test_same_hash_returns_same(self, service):
        """Same hash as previous -> returns ('same', hash)."""
        text = "Hello world"
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value=_sha256(text))
        status, content_hash = await service._detect_change_by_hash(text, "user1", "scout1")
        assert status == "same"
        assert content_hash == _sha256(text)

    @pytest.mark.asyncio
    async def test_different_hash_returns_changed(self, service):
        """Different hash from previous -> returns ('changed', hash)."""
        service.exec_dedup_service.get_latest_content_hash = AsyncMock(return_value="old_hash_value")
        text = "New content"
        status, content_hash = await service._detect_change_by_hash(text, "user1", "scout1")
        assert status == "changed"
        assert content_hash == _sha256(text)


class TestDoubleProbe:
    """Tests for double_probe — two-call verification of changeTracking baseline storage."""

    @pytest.fixture
    def service(self):
        return ScoutService()

    @pytest.mark.asyncio
    async def test_baseline_confirmed_returns_firecrawl(self, service):
        """Call 1 succeeds, Call 2 has previousScrapeAt timestamp → 'firecrawl'."""
        call1_data = {
            "markdown": "# Page",
            "changeTracking": {"changeStatus": "new", "previousScrapeAt": None},
        }
        call2_data = {
            "markdown": "# Page",
            "changeTracking": {
                "changeStatus": "same",
                "previousScrapeAt": "2026-03-04T12:16:54.477+00:00",
            },
        }
        with patch.object(
            service, "_firecrawl_scrape",
            new_callable=AsyncMock, side_effect=[call1_data, call2_data],
        ):
            result = await service.double_probe("https://example.com", "user1", "scout1")
        assert result == "firecrawl"

    @pytest.mark.asyncio
    async def test_baseline_dropped_returns_firecrawl_plain(self, service):
        """Call 1 succeeds, Call 2 has previousScrapeAt=None → 'firecrawl_plain'."""
        call1_data = {
            "markdown": "# Page",
            "changeTracking": {"changeStatus": "new", "previousScrapeAt": None},
        }
        call2_data = {
            "markdown": "# Page",
            "changeTracking": {"changeStatus": "new", "previousScrapeAt": None},
        }
        with patch.object(
            service, "_firecrawl_scrape",
            new_callable=AsyncMock, side_effect=[call1_data, call2_data],
        ):
            result = await service.double_probe("https://example.com", "user1", "scout1")
        assert result == "firecrawl_plain"

    @pytest.mark.asyncio
    async def test_call1_timeout_returns_firecrawl_plain(self, service):
        """Call 1 times out (returns None) → 'firecrawl_plain', no second call."""
        with patch.object(
            service, "_firecrawl_scrape",
            new_callable=AsyncMock, return_value=None,
        ) as mock_scrape:
            result = await service.double_probe("https://example.com", "user1", "scout1")
        assert result == "firecrawl_plain"
        mock_scrape.assert_called_once()  # No second call

    @pytest.mark.asyncio
    async def test_call2_timeout_returns_firecrawl_plain(self, service):
        """Call 1 succeeds, Call 2 times out → 'firecrawl_plain'."""
        call1_data = {
            "markdown": "# Page",
            "changeTracking": {"changeStatus": "new"},
        }
        with patch.object(
            service, "_firecrawl_scrape",
            new_callable=AsyncMock, side_effect=[call1_data, None],
        ):
            result = await service.double_probe("https://example.com", "user1", "scout1")
        assert result == "firecrawl_plain"

    @pytest.mark.asyncio
    async def test_uses_real_tag(self, service):
        """Both calls use user_id#scraper_name as tag."""
        with patch.object(
            service, "_firecrawl_scrape",
            new_callable=AsyncMock, return_value=None,
        ) as mock_scrape:
            await service.double_probe("https://example.com", "user1", "my-scout")
        mock_scrape.assert_called_once_with("https://example.com", tag="user1#my-scout", timeout=30.0)

    @pytest.mark.asyncio
    async def test_truncates_long_tag(self, service):
        """Tags longer than 128 chars are truncated."""
        long_name = "a" * 200
        with patch.object(
            service, "_firecrawl_scrape",
            new_callable=AsyncMock, return_value=None,
        ) as mock_scrape:
            await service.double_probe("https://example.com", "user1", long_name)
        actual_tag = mock_scrape.call_args[1]["tag"]
        assert len(actual_tag) == 128


class TestFirecrawlScrapeUnified:
    """Tests for the unified _firecrawl_scrape method."""

    @pytest.fixture
    def service(self):
        return ScoutService()

    @pytest.mark.asyncio
    async def test_without_tag_excludes_change_tracking(self, service):
        """Plain scrape: formats should be ['markdown'] only."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"markdown": "# Page"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.scout_service.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            result = await service._firecrawl_scrape("https://example.com")

        call_json = mock_client.post.call_args[1]["json"]
        assert call_json["formats"] == ["markdown"]
        assert result == {"markdown": "# Page"}

    @pytest.mark.asyncio
    async def test_with_tag_includes_change_tracking(self, service):
        """changeTracking scrape: formats should include changeTracking object."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"markdown": "# Page", "changeTracking": {"changeStatus": "new"}}
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.scout_service.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            result = await service._firecrawl_scrape("https://example.com", tag="user1#scout1")

        call_json = mock_client.post.call_args[1]["json"]
        assert any(isinstance(f, dict) and f.get("type") == "changeTracking" for f in call_json["formats"])
        assert result["changeTracking"]["changeStatus"] == "new"

    @pytest.mark.asyncio
    async def test_custom_timeout(self, service):
        """Timeout parameter is passed to the HTTP client."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"markdown": "# Page"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.scout_service.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            await service._firecrawl_scrape("https://example.com", timeout=15.0)

        assert mock_client.post.call_args[1]["timeout"] == 15.0
