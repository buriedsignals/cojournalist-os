"""
Unit tests for app.dependencies.providers — DI provider factories.

Tests verify:
- Each factory returns the correct AWS adapter type (with mocked DynamoDB/AWS clients)
- Each factory returns the correct Supabase adapter type when DEPLOYMENT_TARGET=supabase
- Providers are singletons (calling twice returns the same instance)
- Invalid DEPLOYMENT_TARGET raises ValueError
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

import app.dependencies.providers as providers_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_singletons():
    """Reset all module-level singleton globals back to None between tests."""
    providers_module._scout_storage = None
    providers_module._execution_storage = None
    providers_module._run_storage = None
    providers_module._post_snapshot_storage = None
    providers_module._unit_storage = None
    providers_module._seen_record_storage = None
    providers_module._user_storage = None
    providers_module._promise_storage = None
    providers_module._scheduler = None
    providers_module._auth = None
    providers_module._billing = None


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before and after every test."""
    _reset_singletons()
    yield
    _reset_singletons()


# ---------------------------------------------------------------------------
# AWS adapter type mapping
# ---------------------------------------------------------------------------

# (factory_name, adapter_module_path, adapter_class_name, patch_targets)
ADAPTER_CASES = [
    (
        "get_scout_storage",
        "app.adapters.aws.scout_storage",
        "DynamoDBScoutStorage",
        ["app.adapters.aws.scout_storage.get_table"],
    ),
    (
        "get_execution_storage",
        "app.adapters.aws.execution_storage",
        "DynamoDBExecutionStorage",
        ["app.adapters.aws.execution_storage.get_table"],
    ),
    (
        "get_run_storage",
        "app.adapters.aws.run_storage",
        "DynamoDBRunStorage",
        ["app.adapters.aws.run_storage.get_table"],
    ),
    (
        "get_post_snapshot_storage",
        "app.adapters.aws.post_snapshot_storage",
        "DynamoDBPostSnapshotStorage",
        ["app.adapters.aws.post_snapshot_storage.get_table"],
    ),
    (
        "get_unit_storage",
        "app.adapters.aws.unit_storage",
        "DynamoDBUnitStorage",
        ["app.adapters.aws.unit_storage.get_table"],
    ),
    (
        "get_seen_record_storage",
        "app.adapters.aws.seen_record_storage",
        "DynamoDBSeenRecordStorage",
        ["app.adapters.aws.seen_record_storage.get_table"],
    ),
    (
        "get_user_storage",
        "app.adapters.aws.user_storage",
        "DynamoDBUserStorage",
        ["app.adapters.aws.user_storage.get_table"],
    ),
    (
        "get_promise_storage",
        "app.adapters.aws.promise_storage",
        "DynamoDBPromiseStorage",
        ["app.adapters.aws.promise_storage.get_table"],
    ),
    (
        "get_scheduler",
        "app.adapters.aws.scheduler",
        "EventBridgeScheduler",
        [
            "app.adapters.aws.scheduler.boto3",
            "app.adapters.aws.scheduler.get_settings",
        ],
    ),
    (
        "get_auth",
        "app.adapters.aws.auth",
        "MuckRockAuth",
        [],  # MuckRockAuth delegates to existing deps; no __init__ side-effects
    ),
    (
        "get_billing",
        "app.adapters.aws.billing",
        "AWSBilling",
        [],  # AWSBilling delegates to existing deps; no __init__ side-effects
    ),
]


# ---------------------------------------------------------------------------
# Supabase adapter type mapping
# ---------------------------------------------------------------------------

# (factory_name, supabase_adapter_module_path, supabase_adapter_class_name, patch_targets)
SUPABASE_ADAPTER_CASES = [
    (
        "get_scout_storage",
        "app.adapters.supabase.scout_storage",
        "SupabaseScoutStorage",
        [],
    ),
    (
        "get_execution_storage",
        "app.adapters.supabase.execution_storage",
        "SupabaseExecutionStorage",
        [],
    ),
    (
        "get_run_storage",
        "app.adapters.supabase.run_storage",
        "SupabaseRunStorage",
        [],
    ),
    (
        "get_post_snapshot_storage",
        "app.adapters.supabase.post_snapshot_storage",
        "SupabasePostSnapshotStorage",
        [],
    ),
    (
        "get_unit_storage",
        "app.adapters.supabase.unit_storage",
        "SupabaseUnitStorage",
        [],
    ),
    (
        "get_seen_record_storage",
        "app.adapters.supabase.seen_record_storage",
        "SupabaseSeenRecordStorage",
        [],
    ),
    (
        "get_user_storage",
        "app.adapters.supabase.user_storage",
        "SupabaseUserStorage",
        [],
    ),
    (
        "get_promise_storage",
        "app.adapters.supabase.civic_promise_storage",
        "SupabaseCivicPromiseStorage",
        [],
    ),
    (
        "get_scheduler",
        "app.adapters.supabase.scheduler",
        "SupabaseScheduler",
        ["app.adapters.supabase.scheduler.get_settings"],
    ),
    (
        "get_auth",
        "app.adapters.supabase.auth",
        "SupabaseAuth",
        ["app.adapters.supabase.auth.get_settings"],
    ),
    (
        "get_billing",
        "app.adapters.supabase.billing",
        "NoOpBilling",
        [],
    ),
]


# ---------------------------------------------------------------------------
# Returns correct AWS adapter type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory_name,adapter_module,adapter_class,patch_targets", ADAPTER_CASES)
def test_aws_factory_returns_correct_type(
    factory_name, adapter_module, adapter_class, patch_targets
):
    """Each factory should return an instance of the expected AWS adapter class."""
    with patch("app.dependencies.providers.get_settings") as mock_settings:
        mock_settings.return_value.deployment_target = "aws"

        # Patch away all external dependencies of the adapter
        patches = [patch(t, MagicMock()) for t in patch_targets]
        for p in patches:
            p.start()
        try:
            factory = getattr(providers_module, factory_name)
            result = factory()

            mod = importlib.import_module(adapter_module)
            expected_class = getattr(mod, adapter_class)
            assert isinstance(result, expected_class)
        finally:
            for p in patches:
                p.stop()


# ---------------------------------------------------------------------------
# Returns correct Supabase adapter type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory_name,adapter_module,adapter_class,patch_targets", SUPABASE_ADAPTER_CASES)
def test_supabase_factory_returns_correct_type(
    factory_name, adapter_module, adapter_class, patch_targets
):
    """Each factory should return an instance of the expected Supabase adapter class
    when DEPLOYMENT_TARGET='supabase'."""
    with patch("app.dependencies.providers.get_settings") as mock_settings:
        mock_settings.return_value.deployment_target = "supabase"

        patches = [patch(t, MagicMock()) for t in patch_targets]
        for p in patches:
            p.start()
        try:
            factory = getattr(providers_module, factory_name)
            result = factory()

            mod = importlib.import_module(adapter_module)
            expected_class = getattr(mod, adapter_class)
            assert isinstance(result, expected_class)
        finally:
            for p in patches:
                p.stop()


# ---------------------------------------------------------------------------
# Singleton caching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory_name,adapter_module,adapter_class,patch_targets", ADAPTER_CASES)
def test_provider_is_singleton(
    factory_name, adapter_module, adapter_class, patch_targets
):
    """Calling a factory twice should return the identical cached instance."""
    with patch("app.dependencies.providers.get_settings") as mock_settings:
        mock_settings.return_value.deployment_target = "aws"

        patches = [patch(t, MagicMock()) for t in patch_targets]
        for p in patches:
            p.start()
        try:
            factory = getattr(providers_module, factory_name)
            first = factory()
            second = factory()
            assert first is second
        finally:
            for p in patches:
                p.stop()


# ---------------------------------------------------------------------------
# Invalid DEPLOYMENT_TARGET
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory_name,_a,_b,_c", ADAPTER_CASES)
def test_invalid_target_raises_value_error(factory_name, _a, _b, _c):
    """An unrecognised DEPLOYMENT_TARGET should raise ValueError."""
    with patch("app.dependencies.providers.get_settings") as mock_settings:
        mock_settings.return_value.deployment_target = "gcp"
        factory = getattr(providers_module, factory_name)
        with pytest.raises(ValueError, match="Invalid DEPLOYMENT_TARGET"):
            factory()
