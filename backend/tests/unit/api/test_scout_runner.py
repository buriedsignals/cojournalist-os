"""Tests for ScoutRunner — verifies delegation to adapters."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scout_runner import ScoutRunner


@pytest.fixture
def mock_scout_storage():
    return AsyncMock()


@pytest.fixture
def mock_run_storage():
    return AsyncMock()


@pytest.fixture
def scout_runner(mock_scout_storage, mock_run_storage):
    with patch("app.services.scout_runner.get_settings") as mock_settings:
        mock_settings.return_value.internal_service_key = "test-service-key"
        runner = ScoutRunner(
            scout_storage=mock_scout_storage,
            run_storage=mock_run_storage,
        )
    return runner


class TestRunScout:
    @pytest.mark.asyncio
    async def test_returns_error_when_scout_not_found(self, scout_runner, mock_scout_storage):
        mock_scout_storage.get_scout.return_value = None
        result = await scout_runner.run_scout("user-1", "nonexistent")
        assert result["error"] == "Scout not found"
        assert result["scraper_status"] is False

    @pytest.mark.asyncio
    async def test_run_web_scout(self, scout_runner, mock_scout_storage, mock_run_storage):
        mock_scout_storage.get_scout.return_value = {
            "scout_type": "web",
            "url": "https://example.com",
            "criteria": "breaking news",
            "preferred_language": "en",
        }
        with patch("app.services.scout_runner.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"scraper_status": True, "criteria_status": True}
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await scout_runner.run_scout("user-1", "WebScout")

        assert result["scraper_status"] is True
        mock_run_storage.store_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pulse_scout(self, scout_runner, mock_scout_storage, mock_run_storage):
        mock_scout_storage.get_scout.return_value = {
            "scout_type": "pulse",
            "preferred_language": "no",
            "location": {"country": "Norway"},
        }
        with patch("app.services.scout_runner.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"scraper_status": True}
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await scout_runner.run_scout("user-1", "PulseScout")

        assert result["scraper_status"] is True
        call_args = mock_client.post.call_args
        assert "/pulse/execute" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_run_social_scout(self, scout_runner, mock_scout_storage, mock_run_storage):
        mock_scout_storage.get_scout.return_value = {
            "scout_type": "social",
            "platform": "instagram",
            "profile_handle": "testuser",
            "preferred_language": "en",
        }
        with patch("app.services.scout_runner.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"scraper_status": True}
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await scout_runner.run_scout("user-1", "SocialScout")

        assert result["scraper_status"] is True
        call_args = mock_client.post.call_args
        assert "/social/execute" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_run_civic_scout_normalizes_result(self, scout_runner, mock_scout_storage):
        mock_scout_storage.get_scout.return_value = {
            "scout_type": "civic",
            "tracked_urls": ["https://city.gov/meetings"],
            "preferred_language": "en",
        }
        with patch("app.services.scout_runner.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "ok",
                "summary": "Found 2 promises",
                "promises_found": 3,
            }
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await scout_runner.run_scout("user-1", "CivicScout")

        assert result["scraper_status"] is True
        assert result["criteria_status"] is True
        assert result["notification_sent"] is True

    @pytest.mark.asyncio
    async def test_stores_error_on_failure(self, scout_runner, mock_scout_storage, mock_run_storage):
        mock_scout_storage.get_scout.return_value = {
            "scout_type": "web",
            "url": "https://example.com",
            "preferred_language": "en",
        }
        with patch("app.services.scout_runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await scout_runner.run_scout("user-1", "WebScout")

        assert result["scraper_status"] is False
        mock_run_storage.store_run.assert_called_once()


class TestStoreTimeRecord:
    @pytest.mark.asyncio
    async def test_stores_run_record(self, scout_runner, mock_run_storage):
        await scout_runner._store_time_record(
            "user-1", "test-scout", "pulse",
            {"scraper_status": True, "criteria_status": False, "notification_sent": False},
        )
        mock_run_storage.store_run.assert_called_once()
        call_kwargs = mock_run_storage.store_run.call_args.kwargs
        assert call_kwargs["scout_id"] == "test-scout"
        assert call_kwargs["user_id"] == "user-1"
        assert call_kwargs["status"] == "success"
        assert call_kwargs["scout_type"] == "pulse"
