"""Unit tests for MuckRockAuth adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.adapters.aws.auth import MuckRockAuth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    return MuckRockAuth()


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_delegates_to_existing_function(self, adapter):
        """get_current_user delegates to the existing dependency function."""
        mock_request = MagicMock()
        expected_user = {"user_id": "abc123", "credits": 50}

        with patch(
            "app.adapters.aws.auth.get_current_user_dep",
            new_callable=AsyncMock,
            return_value=expected_user,
        ) as mock_fn:
            result = await adapter.get_current_user(mock_request)

        mock_fn.assert_called_once_with(mock_request)
        assert result == expected_user

    @pytest.mark.asyncio
    async def test_propagates_http_exception_401(self, adapter):
        """Propagates HTTPException 401 when session cookie is missing."""
        mock_request = MagicMock()

        with patch(
            "app.adapters.aws.auth.get_current_user_dep",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=401, detail="Missing session cookie"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await adapter.get_current_user(mock_request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_propagates_http_exception_when_user_not_found(self, adapter):
        """Propagates HTTPException when DynamoDB user is not found."""
        mock_request = MagicMock()

        with patch(
            "app.adapters.aws.auth.get_current_user_dep",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=401, detail="User not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await adapter.get_current_user(mock_request)

        assert exc_info.value.detail == "User not found"

    @pytest.mark.asyncio
    async def test_returns_user_dict(self, adapter):
        """Returns the full user dict including nested fields."""
        mock_request = MagicMock()
        user = {
            "user_id": "user1",
            "credits": 100,
            "timezone": "UTC",
            "needs_initialization": False,
            "team": None,
        }

        with patch(
            "app.adapters.aws.auth.get_current_user_dep",
            new_callable=AsyncMock,
            return_value=user,
        ):
            result = await adapter.get_current_user(mock_request)

        assert result["user_id"] == "user1"
        assert result["credits"] == 100


# ---------------------------------------------------------------------------
# get_user_email
# ---------------------------------------------------------------------------

class TestGetUserEmail:
    @pytest.mark.asyncio
    async def test_delegates_to_existing_function(self, adapter):
        """get_user_email delegates to the existing dependency function."""
        with patch(
            "app.adapters.aws.auth.get_user_email_dep",
            new_callable=AsyncMock,
            return_value="user@example.com",
        ) as mock_fn:
            result = await adapter.get_user_email("user1")

        mock_fn.assert_called_once_with("user1")
        assert result == "user@example.com"

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self, adapter):
        """Returns None when the underlying function returns None."""
        with patch(
            "app.adapters.aws.auth.get_user_email_dep",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await adapter.get_user_email("user1")

        assert result is None

    @pytest.mark.asyncio
    async def test_passes_user_id_correctly(self, adapter):
        """Passes the user_id argument through verbatim."""
        with patch(
            "app.adapters.aws.auth.get_user_email_dep",
            new_callable=AsyncMock,
            return_value="a@b.com",
        ) as mock_fn:
            await adapter.get_user_email("specific-user-id-xyz")

        mock_fn.assert_called_once_with("specific-user-id-xyz")

    @pytest.mark.asyncio
    async def test_returns_email_string(self, adapter):
        """Returns the email string from the underlying function."""
        with patch(
            "app.adapters.aws.auth.get_user_email_dep",
            new_callable=AsyncMock,
            return_value="journalist@newsroom.org",
        ):
            result = await adapter.get_user_email("user2")

        assert result == "journalist@newsroom.org"


# ---------------------------------------------------------------------------
# verify_service_key
# ---------------------------------------------------------------------------

class TestVerifyServiceKey:
    @pytest.mark.asyncio
    async def test_returns_true_for_valid_key(self, adapter):
        """Returns True when key matches internal_service_key."""
        with patch("app.adapters.aws.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.internal_service_key = "correct-secret-key"
            mock_settings.return_value = settings
            result = await adapter.verify_service_key("correct-secret-key")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_wrong_key(self, adapter):
        """Returns False when key does not match internal_service_key."""
        with patch("app.adapters.aws.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.internal_service_key = "correct-secret-key"
            mock_settings.return_value = settings
            result = await adapter.verify_service_key("wrong-key")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_empty_key(self, adapter):
        """Returns False when provided key is empty string."""
        with patch("app.adapters.aws.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.internal_service_key = "correct-secret-key"
            mock_settings.return_value = settings
            result = await adapter.verify_service_key("")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_service_key_not_configured(self, adapter):
        """Returns False when internal_service_key is not set in settings."""
        with patch("app.adapters.aws.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.internal_service_key = None
            mock_settings.return_value = settings
            result = await adapter.verify_service_key("any-key")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_service_key_is_empty_string_in_settings(
        self, adapter
    ):
        """Returns False when internal_service_key is empty string in settings."""
        with patch("app.adapters.aws.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.internal_service_key = ""
            mock_settings.return_value = settings
            result = await adapter.verify_service_key("any-key")

        assert result is False

    @pytest.mark.asyncio
    async def test_uses_constant_time_comparison(self, adapter):
        """Uses secrets.compare_digest (constant-time) for key comparison."""
        with patch("app.adapters.aws.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.internal_service_key = "my-secret"
            mock_settings.return_value = settings
            with patch("app.adapters.aws.auth.secrets") as mock_secrets:
                mock_secrets.compare_digest.return_value = True
                result = await adapter.verify_service_key("my-secret")

        mock_secrets.compare_digest.assert_called_once_with("my-secret", "my-secret")
        assert result is True
