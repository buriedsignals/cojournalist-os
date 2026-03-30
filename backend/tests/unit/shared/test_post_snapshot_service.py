"""
Tests for PostSnapshotService.

Verifies delegation to PostSnapshotStoragePort adapter.
"""
import pytest
from unittest.mock import AsyncMock

from app.services.post_snapshot_service import PostSnapshotService


@pytest.fixture
def mock_storage():
    """Mock PostSnapshotStoragePort adapter."""
    return AsyncMock()


@pytest.fixture
def service(mock_storage):
    """PostSnapshotService with mocked adapter."""
    return PostSnapshotService(snapshot_storage=mock_storage)


# ---------------------------------------------------------------------------
# get_snapshot()
# ---------------------------------------------------------------------------


class TestGetSnapshot:
    @pytest.mark.asyncio
    async def test_returns_none_when_adapter_returns_none(self, service, mock_storage):
        mock_storage.get_snapshot.return_value = None
        result = await service.get_snapshot("user-1", "MyScout")
        assert result is None
        mock_storage.get_snapshot.assert_called_once_with("user-1", "MyScout")

    @pytest.mark.asyncio
    async def test_returns_dict_from_adapter(self, service, mock_storage):
        mock_storage.get_snapshot.return_value = {
            "posts": [{"post_id": "p1", "caption_truncated": "Hello"}],
            "platform": "instagram",
            "handle": "testuser",
            "post_count": 1,
        }
        result = await service.get_snapshot("user-1", "MyScout")
        assert result is not None
        assert len(result["posts"]) == 1
        assert result["platform"] == "instagram"

    @pytest.mark.asyncio
    async def test_returns_none_on_adapter_error(self, service, mock_storage):
        mock_storage.get_snapshot.side_effect = Exception("Storage error")
        result = await service.get_snapshot("user-1", "MyScout")
        assert result is None


# ---------------------------------------------------------------------------
# store_snapshot()
# ---------------------------------------------------------------------------


class TestStoreSnapshot:
    @pytest.mark.asyncio
    async def test_delegates_to_adapter(self, service, mock_storage):
        posts = [{"post_id": "p1"}]
        await service.store_snapshot("user-1", "MyScout", posts, "instagram", "testuser")
        # Port signature: store_snapshot(user_id, scout_id, platform, handle, posts)
        mock_storage.store_snapshot.assert_called_once_with(
            "user-1", "MyScout", "instagram", "testuser", posts
        )

    @pytest.mark.asyncio
    async def test_stores_empty_posts(self, service, mock_storage):
        await service.store_snapshot("user-1", "Scout", [], "x", "nobody")
        mock_storage.store_snapshot.assert_called_once_with(
            "user-1", "Scout", "x", "nobody", []
        )


# ---------------------------------------------------------------------------
# delete_snapshot()
# ---------------------------------------------------------------------------


class TestDeleteSnapshot:
    @pytest.mark.asyncio
    async def test_delegates_to_adapter(self, service, mock_storage):
        await service.delete_snapshot("user-1", "MyScout")
        mock_storage.delete_snapshot.assert_called_once_with("user-1", "MyScout")

    @pytest.mark.asyncio
    async def test_does_not_raise_on_error(self, service, mock_storage):
        mock_storage.delete_snapshot.side_effect = Exception("Network error")
        await service.delete_snapshot("user-1", "MyScout")  # Should NOT raise
