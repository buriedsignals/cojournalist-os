# Adapter Pattern Architecture

> **Post-cutover status (2026-04-22):** AWS adapters were retired in the v2 migration.
> Supabase is the only registered backend. The port/adapter pattern is kept because
> the residual FastAPI service still benefits from DI (test seams, future adapters),
> but there is no longer a live second backend. Expect to see `backend/app/adapters/aws/`
> absent and `DEPLOYMENT_TARGET` unused.
>
> Three ports — `PostSnapshotStoragePort`, `SeenRecordStoragePort`, `PromiseStoragePort` —
> were deleted in the post-cutover sweep: the Social Scout baselines, dedup, and Civic
> promise persistence all moved into Supabase Edge Functions and are no longer accessed
> via the FastAPI adapter layer.

coJournalist originally targeted two deployment environments from a single codebase: the
SaaS product running on AWS (DynamoDB + EventBridge + MuckRock OAuth) and the self-hosted
OSS version running on Supabase (PostgreSQL + pg_cron + Supabase Auth). The port/adapter
pattern was the mechanism that made this work without duplicating business logic.

---

## Why This Pattern Exists

Services and routers must never import `boto3`, `asyncpg`, or auth-provider SDKs directly.
Instead, they depend on abstract interfaces (ports). At startup, a factory in `providers.py`
selects the correct concrete implementation (adapter) based on the `DEPLOYMENT_TARGET`
environment variable. Swapping from AWS to Supabase requires only changing one env var — no
code changes.

```
DEPLOYMENT_TARGET=aws       → AWS adapters  (DynamoDB, EventBridge, MuckRock OAuth)
DEPLOYMENT_TARGET=supabase  → Supabase adapters  (PostgreSQL, pg_cron, Supabase Auth)
```

---

## Directory Structure

```
backend/app/
├── ports/                          # Abstract interfaces (ABCs)
│   ├── storage.py                  # 8 storage port interfaces
│   ├── scheduler.py                # SchedulerPort
│   ├── auth.py                     # AuthPort
│   └── billing.py                  # BillingPort
├── adapters/
│   ├── aws/                        # AWS implementations
│   │   ├── dynamo.py               # Shared DynamoDB resource singleton
│   │   ├── scout_storage.py
│   │   ├── execution_storage.py
│   │   ├── run_storage.py
│   │   ├── post_snapshot_storage.py
│   │   ├── unit_storage.py
│   │   ├── seen_record_storage.py
│   │   ├── user_storage.py
│   │   ├── promise_storage.py
│   │   ├── scheduler.py            # EventBridgeScheduler
│   │   ├── auth.py                 # MuckRockAuth
│   │   └── billing.py              # AWSBilling
│   └── supabase/                   # Supabase implementations
│       ├── connection.py           # Shared asyncpg pool singleton
│       ├── utils.py                # Shared helpers
│       ├── scout_storage.py
│       ├── execution_storage.py
│       ├── run_storage.py
│       ├── post_snapshot_storage.py
│       ├── unit_storage.py
│       ├── seen_record_storage.py
│       ├── user_storage.py
│       ├── civic_promise_storage.py
│       ├── scheduler.py            # SupabaseScheduler
│       ├── auth.py                 # SupabaseAuth
│       └── billing.py              # NoOpBilling
└── dependencies/
    ├── __init__.py                 # Re-exports all public symbols
    ├── auth.py                     # get_current_user() — delegates to adapter for Supabase, session cookies for MuckRock
    ├── billing.py                  # Credit/org dependencies
    └── providers.py                # Factory functions + singleton cache
```

---

## Port Interfaces

All 11 port interfaces with their method counts:

| Port | File | Methods | Purpose |
|------|------|---------|---------|
| `ScoutStoragePort` | `ports/storage.py` | 7 | CRUD for scout definitions |
| `ExecutionStoragePort` | `ports/storage.py` | 5 | EXEC# summaries + embedding dedup |
| `RunStoragePort` | `ports/storage.py` | 4 | TIME# run history |
| `PostSnapshotStoragePort` | `ports/storage.py` | 3 | POSTS# social baselines |
| `UnitStoragePort` | `ports/storage.py` | 10 | Atomic fact storage + retrieval |
| `SeenRecordStoragePort` | `ports/storage.py` | 3 | SEEN# URL dedup |
| `UserStoragePort` | `ports/storage.py` | 12 | User prefs + credits/orgs |
| `PromiseStoragePort` | `ports/storage.py` | 6 | PROMISE# civic records |
| `SchedulerPort` | `ports/scheduler.py` | 3 | Create/delete/update schedules |
| `AuthPort` | `ports/auth.py` | 3 | Session auth + service key verification |
| `BillingPort` | `ports/billing.py` | 3 | Credit validation + decrement |

The billing port exists so the `NoOpBilling` adapter (Supabase) can always return success
without any code changes to routers that call `validate_credits()` or `decrement_credit()`.

---

## How DI Wiring Works

`dependencies/providers.py` is the single source of truth for adapter instantiation.
It uses module-level globals as a singleton cache:

```python
# providers.py (simplified)
_scout_storage = None

def get_scout_storage():
    global _scout_storage
    if _scout_storage is None:
        target = _validate_target()   # reads DEPLOYMENT_TARGET, raises if unknown
        if target == "supabase":
            from app.adapters.supabase.scout_storage import SupabaseScoutStorage
            _scout_storage = SupabaseScoutStorage()
        else:
            from app.adapters.aws.scout_storage import DynamoDBScoutStorage
            _scout_storage = DynamoDBScoutStorage()
    return _scout_storage
```

Key properties:
- **Lazy imports** — AWS or Supabase libraries are never imported until first use, so
  the application starts cleanly even if only one target's dependencies are installed.
- **Singleton** — each adapter is instantiated exactly once per process. Stateful
  resources (connection pools, boto3 clients) are shared across requests.
- **Callers always use providers** — services and routers call `get_scout_storage()`,
  never `SupabaseScoutStorage()` directly.

FastAPI dependency injection wires providers into routers via `Depends()`:

```python
# Example router usage
from app.dependencies.providers import get_scout_storage

@router.get("/active")
async def list_scouts(storage: ScoutStoragePort = Depends(get_scout_storage)):
    return await storage.list_scouts(user_id)
```

### Auth Dependency

The `get_current_user()` dependency in `dependencies/auth.py` checks `DEPLOYMENT_TARGET`
and delegates to the correct auth adapter:

- **Supabase:** Extracts Bearer JWT from `Authorization` header, validates with `supabase_jwt_secret`, looks up user in Postgres via `SupabaseAuth`
- **AWS/MuckRock:** Extracts session cookie, validates with `SessionService`, looks up user in DynamoDB

```python
# dependencies/auth.py (simplified)
async def get_current_user(request: Request) -> dict:
    if settings.deployment_target == "supabase":
        auth = get_auth()  # Returns SupabaseAuth with user_storage wired in
        return await auth.get_current_user(request)
    # MuckRock path — session cookie validation
    ...
```

---

## Sync vs Async Concurrency Models

The two adapter sets handle async differently because their underlying libraries have different
concurrency models:

**All services are async.** Services call `await self.storage.method()` which works for both
adapter types:

**AWS Adapters (boto3 — synchronous under the hood)**
- boto3 is synchronous. Each adapter has `*_sync()` methods (direct boto3 calls) and `async`
  wrappers that use `asyncio.to_thread()`.
- Services call the async port methods (e.g. `await self.storage.create_scout()`), which
  internally call `asyncio.to_thread(self.create_scout_sync, ...)`.
- Example:
```python
def create_scout_sync(self, user_id, data):
    self.table.put_item(Item=data)

async def create_scout(self, user_id, data):
    return await asyncio.to_thread(self.create_scout_sync, user_id, data)
```

**Supabase Adapters (asyncpg — natively async)**
- asyncpg is natively async. All methods are `async def` using `await pool.fetchrow(...)`.
- The shared connection pool (`adapters/supabase/connection.py`) uses `statement_cache_size=0`
  for PgBouncer/Supavisor compatibility.

**How services use adapters (constructor injection):**
```python
class FeedSearchService:
    def __init__(self, unit_storage=None):
        if unit_storage is None:
            from app.dependencies.providers import get_unit_storage
            unit_storage = get_unit_storage()
        self.storage = unit_storage

    async def search_semantic(self, user_id, query, ...):
        return await self.storage.search_units(user_id, query_embedding, ...)
```

The optional parameter with lazy default means:
- **Production:** service auto-selects the correct adapter via provider factory
- **Tests:** inject `AsyncMock(spec=UnitStoragePort)` directly

**Critical asyncpg patterns:**
- UUID type casting: Always use `$1::uuid` when comparing string parameters against UUID columns
- Row conversion: All adapters use `row_to_dict()` from `adapters/supabase/utils.py`
- Connection pool: Lazy singleton with double-checked locking via `asyncio.Lock`

---

## Shared Infrastructure Singletons

### AWS: `adapters/aws/dynamo.py`

All AWS adapters share a single `boto3.resource("dynamodb")` instance. The `get_table()`
helper caches Table objects by name (default: `scraping-jobs`):

```python
def get_table(table_name: str = "scraping-jobs"):
    if table_name not in _tables:
        _tables[table_name] = get_dynamo_resource().Table(table_name)
    return _tables[table_name]
```

### Supabase: `adapters/supabase/connection.py`

All Supabase adapters share a single `asyncpg.Pool`. The pool is created lazily on first
use with a double-checked lock (safe for async):

```python
async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _lock:
        if _pool is not None:
            return _pool
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            statement_cache_size=0,   # Required for PgBouncer/Supavisor compatibility
        )
        return _pool
```

`statement_cache_size=0` is required when using Supabase's connection pooler (Supavisor).
Without it, prepared statement IDs desync across pooled connections and queries fail.

---

## How to Add a New Storage Operation

Follow these steps whenever a service needs a new database operation:

**Step 1: Add the abstract method to the port**

```python
# backend/app/ports/storage.py
class ScoutStoragePort(ABC):
    # ... existing methods ...

    @abstractmethod
    async def get_scouts_by_type(self, user_id: str, scout_type: str) -> list[dict]: ...
```

**Step 2: Implement in the AWS adapter**

```python
# backend/app/adapters/aws/scout_storage.py
class DynamoDBScoutStorage(ScoutStoragePort):
    async def get_scouts_by_type(self, user_id: str, scout_type: str) -> list[dict]:
        table = get_table()
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
            FilterExpression=Attr("type").eq(scout_type)
        )
        return response.get("Items", [])
```

**Step 3: Implement in the Supabase adapter**

```python
# backend/app/adapters/supabase/scout_storage.py
class SupabaseScoutStorage(ScoutStoragePort):
    async def get_scouts_by_type(self, user_id: str, scout_type: str) -> list[dict]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT * FROM scouts WHERE user_id = $1 AND type = $2",
            user_id, scout_type
        )
        return [dict(r) for r in rows]
```

**Step 4: Verify tests pass for both adapters**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/ -v
```

Unit tests use `unittest.mock.AsyncMock` to stub both adapters without requiring live
infrastructure. See `backend/tests/CLAUDE.md` for test structure details.

---

## Mirror Pipeline and Adapter Stripping

When code is mirrored to the public OSS repository, the GitHub Action removes the AWS
adapter directory entirely:

```bash
rm -rf backend/app/adapters/aws/
```

The OSS repo ships with only `adapters/supabase/`. Setting `DEPLOYMENT_TARGET=supabase`
is the only valid option in the OSS build. The mirror action validates this:

```bash
DEPLOYMENT_TARGET=supabase python -c "from app.main import app"
```

This ensures the public repo never contains dead code paths that reference removed modules.
