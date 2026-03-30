"""Tests for credit validation with team org support."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from app.utils.credits import validate_user_credits


@pytest.mark.asyncio
async def test_validate_credits_individual():
    """Individual user: reads from USER# balance."""
    mock_svc = AsyncMock()
    mock_svc._get_balance.return_value = 50
    with patch("app.utils.credits.UserService", return_value=mock_svc):
        result = await validate_user_credits("user-1", 10)
        assert result["current_credits"] == 50
        assert result["remaining_after"] == 40
        mock_svc._get_balance.assert_called_once_with("user-1")


@pytest.mark.asyncio
async def test_validate_credits_team():
    """Team user: reads from ORG# balance."""
    mock_svc = AsyncMock()
    mock_svc._get_org_balance.return_value = 4500
    with patch("app.utils.credits.UserService", return_value=mock_svc):
        result = await validate_user_credits("user-1", 10, org_id="org-team-1")
        assert result["current_credits"] == 4500
        assert result["remaining_after"] == 4490
        mock_svc._get_org_balance.assert_called_once_with("org-team-1")


@pytest.mark.asyncio
async def test_validate_credits_team_insufficient():
    """Team user with insufficient org credits raises 402."""
    mock_svc = AsyncMock()
    mock_svc._get_org_balance.return_value = 5
    with patch("app.utils.credits.UserService", return_value=mock_svc):
        with pytest.raises(HTTPException) as exc_info:
            await validate_user_credits("user-1", 20, org_id="org-team-1")
        assert exc_info.value.status_code == 402
