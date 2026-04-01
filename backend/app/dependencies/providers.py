"""
Adapter provider factories. Select AWS or Supabase adapters based on DEPLOYMENT_TARGET.

Each factory lazily imports and caches a singleton adapter instance. Callers always
import from this module — never instantiate adapters directly — so swapping backends
requires only changing DEPLOYMENT_TARGET.
"""
from __future__ import annotations

from app.config import get_settings

# ---------------------------------------------------------------------------
# Cached singleton instances
# ---------------------------------------------------------------------------

_scout_storage = None
_execution_storage = None
_run_storage = None
_post_snapshot_storage = None
_unit_storage = None
_seen_record_storage = None
_user_storage = None
_promise_storage = None
_scheduler = None
_auth = None
_billing = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_target() -> str:
    """Return the deployment target after confirming it is a known value."""
    target = get_settings().deployment_target
    if target not in ("aws", "supabase"):
        raise ValueError(
            f"Invalid DEPLOYMENT_TARGET: {target!r}. Must be 'aws' or 'supabase'."
        )
    return target



# ---------------------------------------------------------------------------
# Provider factories
# ---------------------------------------------------------------------------

def get_scout_storage():
    """Return the ScoutStorage adapter singleton."""
    global _scout_storage
    if _scout_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.scout_storage import SupabaseScoutStorage
            _scout_storage = SupabaseScoutStorage()
        else:
            from app.adapters.aws.scout_storage import DynamoDBScoutStorage
            _scout_storage = DynamoDBScoutStorage()
    return _scout_storage


def get_execution_storage():
    """Return the ExecutionStorage adapter singleton."""
    global _execution_storage
    if _execution_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.execution_storage import SupabaseExecutionStorage
            _execution_storage = SupabaseExecutionStorage()
        else:
            from app.adapters.aws.execution_storage import DynamoDBExecutionStorage
            _execution_storage = DynamoDBExecutionStorage()
    return _execution_storage


def get_run_storage():
    """Return the RunStorage adapter singleton."""
    global _run_storage
    if _run_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.run_storage import SupabaseRunStorage
            _run_storage = SupabaseRunStorage()
        else:
            from app.adapters.aws.run_storage import DynamoDBRunStorage
            _run_storage = DynamoDBRunStorage()
    return _run_storage


def get_post_snapshot_storage():
    """Return the PostSnapshotStorage adapter singleton."""
    global _post_snapshot_storage
    if _post_snapshot_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.post_snapshot_storage import SupabasePostSnapshotStorage
            _post_snapshot_storage = SupabasePostSnapshotStorage()
        else:
            from app.adapters.aws.post_snapshot_storage import DynamoDBPostSnapshotStorage
            _post_snapshot_storage = DynamoDBPostSnapshotStorage()
    return _post_snapshot_storage


def get_unit_storage():
    """Return the UnitStorage adapter singleton."""
    global _unit_storage
    if _unit_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.unit_storage import SupabaseUnitStorage
            _unit_storage = SupabaseUnitStorage()
        else:
            from app.adapters.aws.unit_storage import DynamoDBUnitStorage
            _unit_storage = DynamoDBUnitStorage()
    return _unit_storage


def get_seen_record_storage():
    """Return the SeenRecordStorage adapter singleton."""
    global _seen_record_storage
    if _seen_record_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.seen_record_storage import SupabaseSeenRecordStorage
            _seen_record_storage = SupabaseSeenRecordStorage()
        else:
            from app.adapters.aws.seen_record_storage import DynamoDBSeenRecordStorage
            _seen_record_storage = DynamoDBSeenRecordStorage()
    return _seen_record_storage


def get_user_storage():
    """Return the UserStorage adapter singleton."""
    global _user_storage
    if _user_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.user_storage import SupabaseUserStorage
            _user_storage = SupabaseUserStorage()
        else:
            from app.adapters.aws.user_storage import DynamoDBUserStorage
            _user_storage = DynamoDBUserStorage()
    return _user_storage


def get_promise_storage():
    """Return the PromiseStorage adapter singleton."""
    global _promise_storage
    if _promise_storage is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.civic_promise_storage import SupabaseCivicPromiseStorage
            _promise_storage = SupabaseCivicPromiseStorage()
        else:
            from app.adapters.aws.promise_storage import DynamoDBPromiseStorage
            _promise_storage = DynamoDBPromiseStorage()
    return _promise_storage


def get_scheduler():
    """Return the Scheduler adapter singleton."""
    global _scheduler
    if _scheduler is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.scheduler import SupabaseScheduler
            _scheduler = SupabaseScheduler()
        else:
            from app.adapters.aws.scheduler import EventBridgeScheduler
            _scheduler = EventBridgeScheduler()
    return _scheduler


def get_auth():
    """Return the Auth adapter singleton."""
    global _auth
    if _auth is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.auth import SupabaseAuth
            _auth = SupabaseAuth(user_storage=get_user_storage())
        else:
            from app.adapters.aws.auth import MuckRockAuth
            _auth = MuckRockAuth()
    return _auth


def get_billing():
    """Return the Billing adapter singleton."""
    global _billing
    if _billing is None:
        target = _validate_target()
        if target == "supabase":
            from app.adapters.supabase.billing import NoOpBilling
            _billing = NoOpBilling()
        else:
            from app.adapters.aws.billing import AWSBilling
            _billing = AWSBilling()
    return _billing
