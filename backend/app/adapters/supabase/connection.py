"""asyncpg connection pool singleton for Supabase adapters."""
import asyncio
import asyncpg
from app.config import get_settings

_pool = None
_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _lock:
        if _pool is not None:
            return _pool
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            statement_cache_size=0,  # Required for PgBouncer/Supavisor compatibility
        )
        return _pool
