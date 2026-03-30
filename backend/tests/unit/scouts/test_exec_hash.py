"""Tests for ExecutionDeduplicationService — adapter delegation."""
import pytest
from unittest.mock import AsyncMock

from app.services.execution_deduplication import ExecutionDeduplicationService


class TestStoreExecution:
    @pytest.fixture
    def service(self):
        mock_storage = AsyncMock()
        mock_storage.store_execution.return_value = {"status": "completed"}
        return ExecutionDeduplicationService(execution_storage=mock_storage)

    @pytest.mark.asyncio
    async def test_store_delegates_to_adapter(self, service):
        result = await service.store_execution(
            user_id="user_123", scout_name="my-scout", scout_type="web",
            summary_text="Page updated", is_duplicate=False,
            started_at="2026-03-02T00:00:00Z", content_hash="abc123hash",
        )
        service.storage.store_execution.assert_called_once()
        kwargs = service.storage.store_execution.call_args.kwargs
        assert kwargs["content_hash"] == "abc123hash"
        assert kwargs["scout_name"] == "my-scout"

    @pytest.mark.asyncio
    async def test_store_without_content_hash(self, service):
        await service.store_execution(
            user_id="user_123", scout_name="my-scout", scout_type="web",
            summary_text="Updated", is_duplicate=False, started_at="2026-03-02T00:00:00Z",
        )
        kwargs = service.storage.store_execution.call_args.kwargs
        assert kwargs.get("content_hash") is None

    @pytest.mark.asyncio
    async def test_store_with_provider(self, service):
        await service.store_execution(
            user_id="user_123", scout_name="my-scout", scout_type="web",
            summary_text="Updated", is_duplicate=False, started_at="2026-03-02T00:00:00Z",
            provider="firecrawl_plain",
        )
        kwargs = service.storage.store_execution.call_args.kwargs
        assert kwargs["provider"] == "firecrawl_plain"


class TestGetLatestContentHash:
    @pytest.fixture
    def service(self):
        mock_storage = AsyncMock()
        return ExecutionDeduplicationService(execution_storage=mock_storage)

    @pytest.mark.asyncio
    async def test_delegates_to_adapter(self, service):
        service.storage.get_latest_content_hash.return_value = "abc123"
        result = await service.get_latest_content_hash("user_123", "my-scout")
        assert result == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, service):
        service.storage.get_latest_content_hash.side_effect = Exception("fail")
        result = await service.get_latest_content_hash("user_123", "my-scout")
        assert result is None


class TestGetRecentFindings:
    @pytest.fixture
    def service(self):
        mock_storage = AsyncMock()
        return ExecutionDeduplicationService(execution_storage=mock_storage)

    @pytest.mark.asyncio
    async def test_filters_duplicates(self, service):
        service.storage.get_recent_executions.return_value = [
            {"summary_text": "New finding", "completed_at": "2026-03-02", "is_duplicate": False},
            {"summary_text": "Duplicate", "completed_at": "2026-03-01", "is_duplicate": True},
        ]
        result = await service.get_recent_findings("user_123", "my-scout")
        assert len(result) == 1
        assert result[0]["summary_text"] == "New finding"
