"""Tests for SupabaseUserStorage."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.adapters.supabase.user_storage import SupabaseUserStorage


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def storage(mock_pool):
    s = SupabaseUserStorage()
    s.pool = mock_pool
    return s


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self, storage, mock_pool):
        user_id = str(uuid.uuid4())
        mock_pool.fetchrow = AsyncMock(return_value={
            "user_id": user_id,
            "timezone": "America/New_York",
            "preferred_language": "en",
            "notification_email": "test@example.com",
            "default_location": None,
            "excluded_domains": None,
            "cms_api_url": None,
            "cms_api_token": None,
            "preferences": {},
            "onboarding_completed": True,
            "onboarding_tour_completed": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

        result = await storage.get_user(user_id)
        assert result["timezone"] == "America/New_York"
        assert result["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await storage.get_user(str(uuid.uuid4()))
        assert result is None


class TestCreateOrUpdateUser:
    @pytest.mark.asyncio
    async def test_creates_new_user(self, storage, mock_pool):
        user_id = str(uuid.uuid4())
        mock_pool.fetchrow = AsyncMock(return_value={
            "user_id": user_id,
            "timezone": "UTC",
            "preferred_language": "en",
            "onboarding_completed": False,
        })

        result = await storage.create_or_update_user(user_id, {
            "timezone": "UTC",
            "preferred_language": "en",
        })

        assert result["user_id"] == user_id
        mock_pool.fetchrow.assert_called_once()
        call_sql = mock_pool.fetchrow.call_args[0][0]
        assert "ON CONFLICT" in call_sql

    @pytest.mark.asyncio
    async def test_updates_existing_user(self, storage, mock_pool):
        user_id = str(uuid.uuid4())
        mock_pool.fetchrow = AsyncMock(return_value={
            "user_id": user_id,
            "timezone": "Europe/Berlin",
            "preferred_language": "de",
            "onboarding_completed": True,
        })

        result = await storage.create_or_update_user(user_id, {
            "timezone": "Europe/Berlin",
            "preferred_language": "de",
            "onboarding_completed": True,
        })

        assert result["timezone"] == "Europe/Berlin"


class TestGetCmsConfig:
    @pytest.mark.asyncio
    async def test_returns_cms_config(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "cms_api_url": "https://cms.example.com/api",
            "cms_api_token": "token123",
        })

        result = await storage.get_cms_config(str(uuid.uuid4()))
        assert result["cms_api_url"] == "https://cms.example.com/api"

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_not_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await storage.get_cms_config(str(uuid.uuid4()))
        assert result == {}


class TestCreditMethods:
    @pytest.mark.asyncio
    async def test_get_balance_returns_unlimited(self, storage):
        result = await storage.get_balance("user-1")
        assert result == -1

    @pytest.mark.asyncio
    async def test_decrement_credits_always_succeeds(self, storage):
        result = await storage.decrement_credits("user-1", 10)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_credits_is_noop(self, storage):
        # Should not raise
        await storage.create_credits("user-1", 100, "pro")

    @pytest.mark.asyncio
    async def test_update_credits_is_noop(self, storage):
        # Should not raise
        await storage.update_credits("user-1", {"balance": 50})


class TestOrgMethods:
    @pytest.mark.asyncio
    async def test_create_org_raises(self, storage):
        with pytest.raises(NotImplementedError):
            await storage.create_org("org-1", 100, None, "Test Org")

    @pytest.mark.asyncio
    async def test_get_org_credits_raises(self, storage):
        with pytest.raises(NotImplementedError):
            await storage.get_org_credits("org-1")

    @pytest.mark.asyncio
    async def test_claim_seat_raises(self, storage):
        with pytest.raises(NotImplementedError):
            await storage.claim_seat("org-1", "user-1", "free")
