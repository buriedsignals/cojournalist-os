"""Tests for NoOpBilling."""

import pytest

from app.adapters.supabase.billing import NoOpBilling


@pytest.fixture
def billing():
    return NoOpBilling()


class TestValidateCredits:
    @pytest.mark.asyncio
    async def test_always_returns_true(self, billing):
        assert await billing.validate_credits("user-1", "pulse_search") is True
        assert await billing.validate_credits("user-2", "web_scout") is True
        assert await billing.validate_credits("", "") is True


class TestDecrementCredit:
    @pytest.mark.asyncio
    async def test_always_returns_true(self, billing):
        assert await billing.decrement_credit("user-1", "pulse_search") is True
        assert await billing.decrement_credit("user-2", "web_scout") is True


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_returns_unlimited_balance(self, billing):
        result = await billing.get_balance("user-1")
        assert result["credits"] == -1
        assert result["unlimited"] is True
