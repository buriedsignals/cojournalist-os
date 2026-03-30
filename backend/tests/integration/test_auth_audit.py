"""
Integration tests for the MuckRock auth migration.

Tests the full wiring chain: session creation -> cookie -> endpoint -> service -> DynamoDB mock.
Bypasses OAuth (can't redirect to MuckRock in tests) but tests everything after it.

Categories:
  1. Authentication Chain (5 tests)
  2. Onboarding Flow (3 tests)
  3. Credit Management (4 tests)
  4. Webhook Verification (3 tests)
"""
import hashlib
import hmac as hmac_mod
import time
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth, onboarding
from app.services.session_service import SessionService
from app.services.user_service import UserService, resolve_tier, DEFAULT_FREE_CREDITS
from app.utils.credits import validate_user_credits


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

TEST_SECRET = "test-secret-for-integration-tests"
TEST_USER_ID = "test-user-uuid-1234"
TEST_EMAIL = "testuser@example.com"

# Standard profile and credits records for the mock DynamoDB table
PROFILE_RECORD = {
    "PK": f"USER#{TEST_USER_ID}",
    "SK": "PROFILE",
    "email": TEST_EMAIL,
    "name": "Test User",
    "tier": "free",
    "timezone": "America/New_York",
    "preferred_language": "en",
    "onboarding_completed": True,
    "default_location": None,
    "excluded_domains": [],
    "created_at": "2025-01-01T00:00:00+00:00",
    "last_login": "2025-01-01T00:00:00+00:00",
}

CREDITS_RECORD = {
    "PK": f"USER#{TEST_USER_ID}",
    "SK": "CREDITS",
    "balance": 100,
    "monthly_cap": 100,
    "tier": "free",
    "last_reset_date": "2025-01-01T00:00:00+00:00",
    "update_on": None,
}


def _build_mock_table(profile=None, credits=None):
    """Build a MagicMock DynamoDB table that responds to get_item calls."""
    table = MagicMock()
    _profile = dict(profile) if profile else dict(PROFILE_RECORD)
    _credits = dict(credits) if credits else dict(CREDITS_RECORD)

    def get_item_side_effect(Key):
        pk, sk = Key["PK"], Key["SK"]
        if pk == _profile["PK"] and sk == "PROFILE":
            return {"Item": dict(_profile)}
        if pk == _credits["PK"] and sk == "CREDITS":
            return {"Item": dict(_credits)}
        return {}

    table.get_item = MagicMock(side_effect=get_item_side_effect)
    table.put_item = MagicMock()
    table.update_item = MagicMock()
    return table


def _build_user_service(table):
    """Build a UserService whose .table points to the given mock."""
    with patch("app.services.user_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(aws_region="us-east-1")
        with patch("app.services.user_service.boto3") as mock_boto:
            mock_resource = MagicMock()
            mock_resource.Table.return_value = table
            mock_boto.resource.return_value = mock_resource
            svc = UserService()
    return svc


def _create_test_app(session_svc, user_svc):
    """Create a minimal FastAPI app wired to the given test services."""
    test_app = FastAPI()
    test_app.include_router(auth.router, prefix="/api/auth")
    test_app.include_router(onboarding.router, prefix="/api/onboarding")

    # Patch the lazy-init in the auth router
    def _fake_auth_services():
        return MagicMock(), session_svc, user_svc

    # Patch the lazy-init in the dependencies module
    def _fake_dep_services():
        return session_svc, user_svc

    test_app._auth_get_services_patch = patch(
        "app.routers.auth._get_services", side_effect=_fake_auth_services
    )
    test_app._dep_get_services_patch = patch(
        "app.dependencies.auth._get_services", side_effect=_fake_dep_services
    )
    test_app._auth_get_services_patch.start()
    test_app._dep_get_services_patch.start()

    return test_app


def _cleanup_patches(app):
    app._auth_get_services_patch.stop()
    app._dep_get_services_patch.stop()


# ---------------------------------------------------------------------------
# 1. Authentication Chain
# ---------------------------------------------------------------------------

class TestAuthenticationChain:
    """Tests for session → /auth/me and /auth/status endpoints."""

    def test_session_to_auth_me_returns_user_data(self):
        """Create session -> GET /auth/me returns full user data."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        token = session_svc.create_session(TEST_USER_ID)

        try:
            resp = client.get("/api/auth/me", cookies={"session": token})
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is True
            user = data["user"]
            assert user["user_id"] == TEST_USER_ID
            assert user["email"] == TEST_EMAIL
            assert user["tier"] == "free"
            assert user["credits"] == 100
            assert user["timezone"] == "America/New_York"
            assert user["preferred_language"] == "en"
            assert user["onboarding_completed"] is True
        finally:
            _cleanup_patches(app)

    def test_expired_session_returns_401(self):
        """Expired session -> GET /auth/me returns 401."""
        session_svc = SessionService(secret=TEST_SECRET, max_age=0)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        token = session_svc.create_session(TEST_USER_ID)
        # max_age=0 means the token is already expired at creation time
        time.sleep(1)

        try:
            resp = client.get("/api/auth/me", cookies={"session": token})
            assert resp.status_code == 401
        finally:
            _cleanup_patches(app)

    def test_no_cookie_auth_me_returns_401(self):
        """No cookie -> GET /auth/me returns 401."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        try:
            resp = client.get("/api/auth/me")
            assert resp.status_code == 401
        finally:
            _cleanup_patches(app)

    def test_no_cookie_auth_status_returns_unauthenticated(self):
        """No cookie -> GET /auth/status returns {authenticated: false}."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        try:
            resp = client.get("/api/auth/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is False
        finally:
            _cleanup_patches(app)

    def test_valid_cookie_auth_status_returns_authenticated(self):
        """Valid cookie -> GET /auth/status returns {authenticated: true, user: {...}}."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        token = session_svc.create_session(TEST_USER_ID)

        try:
            resp = client.get("/api/auth/status", cookies={"session": token})
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is True
            assert data["user"]["user_id"] == TEST_USER_ID
            assert data["user"]["email"] == TEST_EMAIL
        finally:
            _cleanup_patches(app)


# ---------------------------------------------------------------------------
# 2. Onboarding Flow
# ---------------------------------------------------------------------------

class TestOnboardingFlow:
    """Tests for /onboarding/initialize, /onboarding/status, /onboarding/tour-complete."""

    def test_initialize_sets_preferences_and_marks_complete(self):
        """POST /onboarding/initialize sets timezone, language, and marks onboarding complete."""
        session_svc = SessionService(secret=TEST_SECRET)
        # Start with onboarding_completed=False
        profile = dict(PROFILE_RECORD, onboarding_completed=False)
        table = _build_mock_table(profile=profile)
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        token = session_svc.create_session(TEST_USER_ID)

        # We also need to patch UserService() inside the onboarding router,
        # since it creates its own instance.
        with patch("app.routers.onboarding.UserService", return_value=user_svc):
            try:
                # Initialize
                resp = client.post(
                    "/api/onboarding/initialize",
                    json={"timezone": "Europe/Zurich", "preferred_language": "de"},
                    cookies={"session": token},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "initialized"

                # Verify update_preferences was called with correct args
                user_svc.table.update_item.assert_called()
                call_kwargs = user_svc.table.update_item.call_args
                expr_values = call_kwargs.kwargs.get(
                    "ExpressionAttributeValues",
                    call_kwargs[1].get("ExpressionAttributeValues", {}),
                )
                assert expr_values.get(":timezone") == "Europe/Zurich"
                assert expr_values.get(":preferred_language") == "de"
                assert expr_values.get(":onboarding_completed") is True

                # Now check /onboarding/status. Since the mock table won't
                # reflect the update (it's a mock), we modify the mock to
                # return the updated profile for the status check.
                updated_profile = dict(profile, onboarding_completed=True)
                table.get_item.side_effect = None
                table.get_item = MagicMock(
                    side_effect=lambda Key: (
                        {"Item": dict(updated_profile)}
                        if Key["SK"] == "PROFILE"
                        else {"Item": dict(CREDITS_RECORD)}
                    )
                )

                resp = client.get(
                    "/api/onboarding/status",
                    cookies={"session": token},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["onboarding_completed"] is True
                assert data["needs_initialization"] is False
            finally:
                _cleanup_patches(app)

    def test_initialize_invalid_timezone_returns_400(self):
        """POST /onboarding/initialize with invalid timezone -> 400."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        token = session_svc.create_session(TEST_USER_ID)

        with patch("app.routers.onboarding.UserService", return_value=user_svc):
            try:
                resp = client.post(
                    "/api/onboarding/initialize",
                    json={"timezone": "Not/A/Timezone", "preferred_language": "en"},
                    cookies={"session": token},
                )
                assert resp.status_code == 400
                assert "Invalid timezone" in resp.json()["detail"]
            finally:
                _cleanup_patches(app)

    def test_tour_complete_updates_flag(self):
        """POST /onboarding/tour-complete sets onboarding_tour_completed."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)
        client = TestClient(app)

        token = session_svc.create_session(TEST_USER_ID)

        with patch("app.routers.onboarding.UserService", return_value=user_svc):
            try:
                resp = client.post(
                    "/api/onboarding/tour-complete",
                    cookies={"session": token},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "completed"

                # Verify update_preferences was called with the tour flag
                call_kwargs = user_svc.table.update_item.call_args
                expr_values = call_kwargs.kwargs.get(
                    "ExpressionAttributeValues",
                    call_kwargs[1].get("ExpressionAttributeValues", {}),
                )
                assert expr_values.get(":onboarding_tour_completed") is True
            finally:
                _cleanup_patches(app)


# ---------------------------------------------------------------------------
# 3. Credit Management
# ---------------------------------------------------------------------------

class TestCreditManagement:
    """Tests for credit decrement, tier resolution, and credit validation."""

    def test_credit_decrement_basic(self):
        """Seed 100 credits, decrement 5, verify balance is 95."""
        table = _build_mock_table()
        user_svc = _build_user_service(table)

        # After decrement, mock the balance query to return 95
        original_get_item = table.get_item.side_effect

        def after_decrement(Key):
            result = original_get_item(Key)
            if Key.get("SK") == "CREDITS" and result.get("Item"):
                result["Item"]["balance"] = 95
            return result

        # Do the decrement — should not raise
        user_svc.decrement_credits(TEST_USER_ID, 5)

        # Verify update_item was called with correct condition
        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args
        assert call_kwargs.kwargs["ConditionExpression"] == "balance >= :cost"
        assert call_kwargs.kwargs["ExpressionAttributeValues"][":cost"] == 5

        # Simulate post-decrement balance check
        table.get_item.side_effect = after_decrement
        balance = user_svc._get_balance(TEST_USER_ID)
        assert balance == 95

    def test_credit_decrement_insufficient_raises(self):
        """Seed 2 credits, attempt decrement of 5 -> ConditionalCheckFailedException."""
        credits = dict(CREDITS_RECORD, balance=2)
        table = _build_mock_table(credits=credits)
        user_svc = _build_user_service(table)

        # Simulate DynamoDB conditional check failure
        table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Condition not met"}},
            "UpdateItem",
        )

        with pytest.raises(ClientError) as exc_info:
            user_svc.decrement_credits(TEST_USER_ID, 5)

        assert exc_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"

        # Verify balance unchanged
        balance = user_svc._get_balance(TEST_USER_ID)
        assert balance == 2

    def test_tier_resolution_from_entitlements(self):
        """resolve_tier correctly picks highest tier from org entitlements."""
        # Free (no entitlements)
        tier, credits, update_on = resolve_tier([])
        assert tier == "free"
        assert credits == DEFAULT_FREE_CREDITS

        # Free (non-cojournalist entitlements only)
        tier, credits, update_on = resolve_tier([
            {"entitlements": [{"name": "muckrock-pro", "resources": {}}]}
        ])
        assert tier == "free"
        assert credits == DEFAULT_FREE_CREDITS

        # Pro
        tier, credits, update_on = resolve_tier([
            {"entitlements": [{"name": "cojournalist-pro", "resources": {"monthly_credits": 750}}]}
        ])
        assert tier == "pro"
        assert credits == 750

        # Team
        tier, credits, update_on = resolve_tier([
            {"entitlements": [{"name": "cojournalist-team", "resources": {"monthly_credits": 5000}}]}
        ])
        assert tier == "team"
        assert credits == 5000

        # Mixed: pro + team across orgs -> team wins
        tier, credits, update_on = resolve_tier([
            {"entitlements": [{"name": "cojournalist-pro", "resources": {"monthly_credits": 750}}]},
            {"entitlements": [{"name": "cojournalist-team", "resources": {"monthly_credits": 5000}}]},
        ])
        assert tier == "team"
        assert credits == 5000

    @pytest.mark.asyncio
    async def test_credit_validation_raises_402(self):
        """validate_user_credits raises 402 when balance < required."""
        credits = dict(CREDITS_RECORD, balance=5)
        table = _build_mock_table(credits=credits)
        user_svc = _build_user_service(table)

        with patch("app.utils.credits.UserService", return_value=user_svc):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await validate_user_credits(TEST_USER_ID, 10)

            assert exc_info.value.status_code == 402
            detail = exc_info.value.detail
            assert detail["error"] == "insufficient_credits"
            assert detail["current_credits"] == 5
            assert detail["required_credits"] == 10
            assert detail["shortfall"] == 5


# ---------------------------------------------------------------------------
# 4. Webhook Verification
# ---------------------------------------------------------------------------

class TestWebhookVerification:
    """Tests for HMAC signature verification on POST /auth/webhook."""

    WEBHOOK_SECRET = "webhook-test-secret"

    def _build_webhook_app(self):
        """Build a test app with mocked settings for webhook verification."""
        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc = _build_user_service(table)
        app = _create_test_app(session_svc, user_svc)

        # Patch get_settings in the auth router to return our webhook secret
        mock_settings = MagicMock()
        mock_settings.muckrock_client_secret = self.WEBHOOK_SECRET
        app._settings_patch = patch("app.routers.auth.get_settings", return_value=mock_settings)
        app._settings_patch.start()

        return app

    def _cleanup_webhook(self, app):
        app._settings_patch.stop()
        _cleanup_patches(app)

    def _sign(self, timestamp, event_type, uuids):
        message = str(timestamp) + event_type + "".join(uuids)
        return hmac_mod.new(
            self.WEBHOOK_SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def test_valid_signature_accepted(self):
        """Valid HMAC signature -> 200."""
        app = self._build_webhook_app()
        client = TestClient(app)

        ts = str(int(time.time()))
        event_type = "user"
        uuids = ["uuid-1", "uuid-2"]
        sig = self._sign(ts, event_type, uuids)

        # Mock the muckrock client's fetch_user_data to avoid real HTTP calls.
        # The _get_services mock returns a MagicMock as the muckrock client,
        # so its async methods need to be AsyncMocks.
        from unittest.mock import AsyncMock

        # Re-patch _get_services to provide an AsyncMock muckrock client
        app._auth_get_services_patch.stop()
        mock_muckrock = MagicMock()
        mock_muckrock.fetch_user_data = AsyncMock(return_value={
            "uuid": "uuid-1", "email": "u@example.com", "name": "User",
            "organizations": [],
        })

        session_svc = SessionService(secret=TEST_SECRET)
        table = _build_mock_table()
        user_svc_for_webhook = _build_user_service(table)

        app._auth_get_services_patch = patch(
            "app.routers.auth._get_services",
            side_effect=lambda: (mock_muckrock, session_svc, user_svc_for_webhook),
        )
        app._auth_get_services_patch.start()

        try:
            resp = client.post(
                "/api/auth/webhook",
                json={
                    "timestamp": ts,
                    "type": event_type,
                    "uuids": uuids,
                    "signature": sig,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        finally:
            self._cleanup_webhook(app)

    def test_invalid_signature_rejected(self):
        """Wrong HMAC signature -> 401."""
        app = self._build_webhook_app()
        client = TestClient(app)

        ts = str(int(time.time()))

        try:
            resp = client.post(
                "/api/auth/webhook",
                json={
                    "timestamp": ts,
                    "type": "user",
                    "uuids": ["uuid-1"],
                    "signature": "definitely-wrong-signature",
                },
            )
            assert resp.status_code == 401
            assert "Invalid webhook signature" in resp.json()["detail"]
        finally:
            self._cleanup_webhook(app)

    def test_expired_timestamp_rejected(self):
        """Timestamp > 5 minutes old -> 401."""
        app = self._build_webhook_app()
        client = TestClient(app)

        # 10 minutes ago
        ts = str(int(time.time()) - 600)
        event_type = "user"
        uuids = ["uuid-1"]
        sig = self._sign(ts, event_type, uuids)

        try:
            resp = client.post(
                "/api/auth/webhook",
                json={
                    "timestamp": ts,
                    "type": event_type,
                    "uuids": uuids,
                    "signature": sig,
                },
            )
            assert resp.status_code == 401
            assert "expired" in resp.json()["detail"].lower()
        finally:
            self._cleanup_webhook(app)
