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
            # Disable JIT: Supavisor's transaction-pooled connections get torn
            # down before the JIT warm-up amortizes, so the first query on
            # every fresh connection pays 200–800ms for nothing. Off is the
            # right default for Supabase's pooler.
            server_settings={"jit": "off"},
        )
        return _pool
