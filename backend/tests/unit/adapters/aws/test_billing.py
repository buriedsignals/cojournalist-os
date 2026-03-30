"""Unit tests for AWSBilling adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.adapters.aws.billing import AWSBilling


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    return AWSBilling()


# ---------------------------------------------------------------------------
# validate_credits
# ---------------------------------------------------------------------------

class TestValidateCredits:
    @pytest.mark.asyncio
    async def test_returns_true_when_credits_sufficient(self, adapter):
        """Returns True when validate_credits_dep succeeds (no exception)."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            return_value={"current_credits": 50, "required": 7, "remaining_after": 43},
        ) as mock_fn:
            result = await adapter.validate_credits("user1", "pulse")

        assert result is True
        mock_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_402(self, adapter):
        """Returns False when validate_credits_dep raises HTTPException 402."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=402, detail="insufficient_credits"),
        ):
            result = await adapter.validate_credits("user1", "pulse")

        assert result is False

    @pytest.mark.asyncio
    async def test_propagates_non_402_http_exception(self, adapter):
        """Propagates HTTPException with status != 402 (e.g. 500)."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=500, detail="server error"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await adapter.validate_credits("user1", "pulse")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_passes_correct_amount_for_pulse(self, adapter):
        """Passes the CREDIT_COSTS cost for 'pulse' (7) to validate_credits_dep."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            return_value={"current_credits": 10, "required": 7, "remaining_after": 3},
        ) as mock_fn:
            await adapter.validate_credits("user1", "pulse")

        _, call_args = mock_fn.call_args[0], mock_fn.call_args
        args = mock_fn.call_args[0]
        assert args[0] == "user1"
        assert args[1] == 7  # CREDIT_COSTS["pulse"]

    @pytest.mark.asyncio
    async def test_passes_correct_amount_for_website_extraction(self, adapter):
        """Passes the CREDIT_COSTS cost for 'website_extraction' (1) to validate_credits_dep."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            return_value={"current_credits": 10, "required": 1, "remaining_after": 9},
        ) as mock_fn:
            await adapter.validate_credits("user1", "website_extraction")

        args = mock_fn.call_args[0]
        assert args[1] == 1  # CREDIT_COSTS["website_extraction"]

    @pytest.mark.asyncio
    async def test_defaults_to_1_for_unknown_operation(self, adapter):
        """Defaults to cost of 1 when the operation key is not in CREDIT_COSTS."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            return_value={"current_credits": 10, "required": 1, "remaining_after": 9},
        ) as mock_fn:
            await adapter.validate_credits("user1", "unknown_operation")

        args = mock_fn.call_args[0]
        assert args[1] == 1

    @pytest.mark.asyncio
    async def test_passes_user_id_correctly(self, adapter):
        """Passes user_id verbatim to the underlying function."""
        with patch(
            "app.adapters.aws.billing.validate_credits_dep",
            new_callable=AsyncMock,
            return_value={"current_credits": 50, "required": 7, "remaining_after": 43},
        ) as mock_fn:
            await adapter.validate_credits("specific-user-xyz", "pulse")

        args = mock_fn.call_args[0]
        assert args[0] == "specific-user-xyz"


# ---------------------------------------------------------------------------
# decrement_credit
# ---------------------------------------------------------------------------

class TestDecrementCredit:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, adapter):
        """Returns True when the underlying decrement_credit_dep succeeds."""
        with patch(
            "app.adapters.aws.billing.decrement_credit_dep",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fn:
            result = await adapter.decrement_credit("user1", "pulse")

        assert result is True
        mock_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_insufficient_credits(self, adapter):
        """Returns False when decrement_credit_dep returns False (insufficient credits)."""
        with patch(
            "app.adapters.aws.billing.decrement_credit_dep",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await adapter.decrement_credit("user1", "pulse")

        assert result is False

    @pytest.mark.asyncio
    async def test_passes_correct_amount_for_pulse(self, adapter):
        """Passes amount=7 (CREDIT_COSTS['pulse']) to decrement_credit_dep."""
        with patch(
            "app.adapters.aws.billing.decrement_credit_dep",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fn:
            await adapter.decrement_credit("user1", "pulse")

        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["amount"] == 7  # CREDIT_COSTS["pulse"]

    @pytest.mark.asyncio
    async def test_passes_correct_amount_for_civic(self, adapter):
        """Passes amount=20 (CREDIT_COSTS['civic']) to decrement_credit_dep."""
        with patch(
            "app.adapters.aws.billing.decrement_credit_dep",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fn:
            await adapter.decrement_credit("user1", "civic")

        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["amount"] == 20  # CREDIT_COSTS["civic"]

    @pytest.mark.asyncio
    async def test_defaults_to_1_for_unknown_operation(self, adapter):
        """Defaults to amount=1 when the operation key is not in CREDIT_COSTS."""
        with patch(
            "app.adapters.aws.billing.decrement_credit_dep",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fn:
            await adapter.decrement_credit("user1", "unknown_operation")

        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["amount"] == 1

    @pytest.mark.asyncio
    async def test_passes_user_id_correctly(self, adapter):
        """Passes user_id verbatim to decrement_credit_dep."""
        with patch(
            "app.adapters.aws.billing.decrement_credit_dep",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fn:
            await adapter.decrement_credit("specific-user-xyz", "pulse")

        args = mock_fn.call_args[0]
        assert args[0] == "specific-user-xyz"


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

class TestGetBalance:
    @pytest.mark.asyncio
    async def test_returns_dict_with_balance(self, adapter):
        """Returns a dict with a 'balance' key containing the credit count."""
        with patch(
            "app.adapters.aws.billing.get_user_credits_dep",
            new_callable=AsyncMock,
            return_value=42,
        ):
            result = await adapter.get_balance("user1")

        assert result == {"balance": 42}

    @pytest.mark.asyncio
    async def test_returns_zero_balance_when_credits_zero(self, adapter):
        """Returns {'balance': 0} when user has no credits."""
        with patch(
            "app.adapters.aws.billing.get_user_credits_dep",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await adapter.get_balance("user1")

        assert result == {"balance": 0}

    @pytest.mark.asyncio
    async def test_delegates_to_get_user_credits_dep(self, adapter):
        """Delegates to get_user_credits_dep with the user_id."""
        with patch(
            "app.adapters.aws.billing.get_user_credits_dep",
            new_callable=AsyncMock,
            return_value=100,
        ) as mock_fn:
            await adapter.get_balance("user-abc")

        mock_fn.assert_called_once_with("user-abc")

    @pytest.mark.asyncio
    async def test_passes_user_id_correctly(self, adapter):
        """Passes user_id verbatim to get_user_credits_dep."""
        with patch(
            "app.adapters.aws.billing.get_user_credits_dep",
            new_callable=AsyncMock,
            return_value=5,
        ) as mock_fn:
            await adapter.get_balance("specific-user-xyz")

        mock_fn.assert_called_once_with("specific-user-xyz")

    @pytest.mark.asyncio
    async def test_balance_reflects_underlying_value(self, adapter):
        """The 'balance' value in the returned dict matches the dep's return value."""
        with patch(
            "app.adapters.aws.billing.get_user_credits_dep",
            new_callable=AsyncMock,
            return_value=999,
        ):
            result = await adapter.get_balance("user1")

        assert result["balance"] == 999
