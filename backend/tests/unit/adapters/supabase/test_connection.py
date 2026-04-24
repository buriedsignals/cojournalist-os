"""Tests for asyncpg connection pool singleton."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset the pool singleton between tests."""
    import app.adapters.supabase.connection as conn_module
    conn_module._pool = None
    yield
    conn_module._pool = None


@pytest.mark.asyncio
async def test_pool_is_created_lazily():
    """Pool should not be created at import time."""
    import app.adapters.supabase.connection as conn_module

    # Verify pool starts as None (not created at import)
    assert conn_module._pool is None


@pytest.mark.asyncio
async def test_get_pool_creates_pool_with_correct_params():
    """get_pool() should create pool with required parameters including statement_cache_size=0."""
    mock_pool = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = "postgresql://user:pass@localhost/db"

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
        with patch("app.adapters.supabase.connection.get_settings", return_value=mock_settings):
            from app.adapters.supabase.connection import get_pool

            result = await get_pool()

    assert result is mock_pool
    mock_create.assert_awaited_once_with(
        dsn="postgresql://user:pass@localhost/db",
        min_size=2,
        max_size=10,
        command_timeout=30,
        statement_cache_size=0,
        server_settings={"jit": "off"},
    )


@pytest.mark.asyncio
async def test_get_pool_returns_same_pool_on_second_call():
    """Second call to get_pool() should return the same pool without creating a new one."""
    mock_pool = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = "postgresql://user:pass@localhost/db"

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
        with patch("app.adapters.supabase.connection.get_settings", return_value=mock_settings):
            from app.adapters.supabase.connection import get_pool

            first = await get_pool()
            second = await get_pool()

    assert first is second
    # create_pool should only be called once
    assert mock_create.await_count == 1


@pytest.mark.asyncio
async def test_statement_cache_size_is_zero():
    """statement_cache_size=0 must be passed for PgBouncer/Supavisor compatibility."""
    mock_pool = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = "postgresql://user:pass@localhost/db"

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
        with patch("app.adapters.supabase.connection.get_settings", return_value=mock_settings):
            from app.adapters.supabase.connection import get_pool

            await get_pool()

    _, kwargs = mock_create.call_args
    assert kwargs.get("statement_cache_size") == 0
    # JIT disabled for Supavisor compatibility (cold-connection warm-up tax).
    assert kwargs.get("server_settings", {}).get("jit") == "off"
