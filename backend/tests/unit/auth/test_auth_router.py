"""
Unit tests for the MuckRock OAuth auth router.

Tests verify:
1. GET /api/auth/login redirects to MuckRock authorize URL
2. GET /api/auth/me without cookie returns 401
3. GET /api/auth/me with valid session returns user data
4. POST /api/auth/logout clears the session cookie
5. GET /api/auth/callback without code returns 400
6. POST /api/auth/webhook with invalid signature returns 401

NOTE: Uses a standalone FastAPI app with just the auth router to avoid
importing app.main (which pulls in all routers and their dependencies).
"""
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth as auth_module

# Build a minimal test app with only the auth router
_test_app = FastAPI()
_test_app.include_router(auth_module.router, prefix="/api/auth")

client = TestClient(_test_app)


@pytest.fixture(autouse=True)
def reset_services():
    """Reset lazy-initialized services before each test."""
    auth_module._muckrock_client = None
    auth_module._session_service = None
    auth_module._user_service = None
    auth_module._pending_states.clear()
    yield
    auth_module._muckrock_client = None
    auth_module._session_service = None
    auth_module._user_service = None
    auth_module._pending_states.clear()


class TestLogin:
    """Tests for GET /api/auth/login."""

    def test_login_redirects_to_muckrock(self):
        """Login should return 302 redirect to accounts.muckrock.com with client_id and state."""
        response = client.get("/api/auth/login", follow_redirects=False)
        assert response.status_code == 302
        location = response.headers["location"]
        assert "accounts.muckrock.com" in location
        assert "client_id=" in location
        assert "state=" in location
        assert "response_type=code" in location

    def test_login_stores_state_token(self):
        """Login should store the CSRF state token for later verification."""
        client.get("/api/auth/login", follow_redirects=False)
        assert len(auth_module._pending_states) == 1


class TestMe:
    """Tests for GET /api/auth/me."""

    def test_me_without_cookie_returns_401(self):
        """Request without session cookie should return 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_session_returns_401(self):
        """Request with invalid session cookie should return 401."""
        mock_session_svc = MagicMock()
        mock_session_svc.validate_session.return_value = None
        mock_user_svc = AsyncMock()
        mock_muckrock = MagicMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        response = client.get("/api/auth/me", cookies={"session": "invalid-token"})
        assert response.status_code == 401

    def test_me_with_valid_session_returns_user(self):
        """Request with valid session cookie should return flat user dict (no authenticated wrapper)."""
        mock_session_svc = MagicMock()
        mock_session_svc.validate_session.return_value = {"sub": "user-uuid-123"}

        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = {
            "user_id": "user-uuid-123",
            "tier": "pro",
            "credits": 500,
            "timezone": "America/New_York",
            "preferred_language": "en",
            "onboarding_completed": True,
            "default_location": None,
            "excluded_domains": [],
        }

        mock_muckrock = MagicMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        response = client.get("/api/auth/me", cookies={"session": "valid-token"})
        assert response.status_code == 200
        data = response.json()
        # /me returns a flat user dict — no "authenticated" wrapper
        assert "authenticated" not in data
        assert data["user_id"] == "user-uuid-123"
        assert data["tier"] == "pro"
        assert data["needs_initialization"] is False

    def test_me_returns_upgrade_url_with_source(self):
        """Response from /me should include upgrade_url with source=cojournalist."""
        mock_session_svc = MagicMock()
        mock_session_svc.validate_session.return_value = {"sub": "user-uuid-789"}

        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = {
            "user_id": "user-uuid-789",
            "tier": "free",
            "credits": 50,
            "timezone": "UTC",
            "preferred_language": "en",
            "onboarding_completed": True,
            "default_location": None,
            "excluded_domains": [],
        }

        mock_muckrock = MagicMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        mock_settings = MagicMock()
        mock_settings.muckrock_pro_plan_url = "https://accounts.muckrock.com/plans/70-cojournalist-pro/"

        with patch("app.dependencies.auth.get_settings", return_value=mock_settings):
            response = client.get("/api/auth/me", cookies={"session": "valid-token"})

        assert response.status_code == 200
        data = response.json()
        assert "upgrade_url" in data
        assert "source=cojournalist" in data["upgrade_url"]
        assert data["upgrade_url"].startswith("https://accounts.muckrock.com/plans/")

    def test_me_with_valid_session_but_no_user_returns_401(self):
        """If session is valid but user doesn't exist, return 401."""
        mock_session_svc = MagicMock()
        mock_session_svc.validate_session.return_value = {"sub": "deleted-user"}

        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = None

        mock_muckrock = MagicMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        response = client.get("/api/auth/me", cookies={"session": "valid-token"})
        assert response.status_code == 401


class TestStatus:
    """Tests for GET /api/auth/status."""

    def test_status_without_cookie_returns_unauthenticated(self):
        """Anonymous request should return authenticated: false."""
        response = client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None

    def test_status_with_valid_session_returns_user(self):
        """Authenticated request should return user data."""
        mock_session_svc = MagicMock()
        mock_session_svc.validate_session.return_value = {"sub": "user-uuid-456"}

        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = {
            "user_id": "user-uuid-456",
            "email": "status@example.com",
            "name": "Status User",
            "tier": "free",
            "credits": 100,
            "timezone": None,
            "preferred_language": "en",
            "onboarding_completed": False,
            "default_location": None,
            "excluded_domains": [],
        }

        mock_muckrock = MagicMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        response = client.get("/api/auth/status", cookies={"session": "valid-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["user_id"] == "user-uuid-456"

    def test_status_with_invalid_session_returns_unauthenticated(self):
        """Invalid session should return authenticated: false (not 401)."""
        mock_session_svc = MagicMock()
        mock_session_svc.validate_session.return_value = None
        mock_user_svc = AsyncMock()
        mock_muckrock = MagicMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        response = client.get("/api/auth/status", cookies={"session": "bad-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None


class TestLogout:
    """Tests for POST /api/auth/logout."""

    def test_logout_returns_success(self):
        """Logout should return logged_out status."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "logged_out"

    def test_logout_clears_session_cookie(self):
        """Logout should set the session cookie to expire."""
        response = client.post("/api/auth/logout")
        # Check that a Set-Cookie header is present that clears the session
        set_cookie = response.headers.get("set-cookie", "")
        assert "session=" in set_cookie


class TestCallback:
    """Tests for GET /api/auth/callback."""

    def test_callback_without_code_returns_400(self):
        """Callback without authorization code should return 400."""
        response = client.get("/api/auth/callback", follow_redirects=False)
        assert response.status_code == 400

    def test_callback_without_state_returns_400(self):
        """Callback with code but no state should return 400."""
        response = client.get(
            "/api/auth/callback?code=test-code", follow_redirects=False
        )
        assert response.status_code == 400

    def test_callback_with_invalid_state_redirects_to_login(self):
        """Callback with unrecognized state should redirect to login with error."""
        response = client.get(
            "/api/auth/callback?code=test-code&state=bogus",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=invalid_state" in response.headers["location"]

    def test_callback_with_oauth_error_redirects(self):
        """Callback with error param from provider should redirect to login."""
        response = client.get(
            "/api/auth/callback?error=access_denied",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=oauth_denied" in response.headers["location"]


class TestWebhook:
    """Tests for POST /api/auth/webhook."""

    def test_webhook_missing_fields_returns_400(self):
        """Webhook without required fields should return 400."""
        response = client.post("/api/auth/webhook", json={"type": "user"})
        assert response.status_code == 400

    def test_webhook_invalid_signature_returns_401(self):
        """Webhook with wrong HMAC signature should return 401."""
        mock_muckrock = MagicMock()
        mock_session_svc = MagicMock()
        mock_user_svc = AsyncMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        ts = str(int(time.time()))
        response = client.post(
            "/api/auth/webhook",
            json={
                "timestamp": ts,
                "type": "user",
                "uuids": ["uuid-1"],
                "signature": "wrong-signature",
            },
        )
        assert response.status_code == 401

    def test_webhook_expired_timestamp_returns_401(self):
        """Webhook with timestamp older than 5 minutes should return 401."""
        mock_muckrock = MagicMock()
        mock_session_svc = MagicMock()
        mock_user_svc = AsyncMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        # Timestamp from 10 minutes ago
        ts = str(int(time.time()) - 600)
        event_type = "user"
        uuids = ["uuid-1"]
        secret = ""  # Default empty secret from config

        message = ts + event_type + "".join(uuids)
        sig = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        response = client.post(
            "/api/auth/webhook",
            json={
                "timestamp": ts,
                "type": event_type,
                "uuids": uuids,
                "signature": sig,
            },
        )
        assert response.status_code == 401

    def test_webhook_valid_user_event(self):
        """Valid webhook with correct signature should process user update."""
        mock_muckrock = MagicMock()
        mock_muckrock.fetch_user_data = AsyncMock(
            return_value={
                "uuid": "uuid-1",
                "email": "webhook@example.com",
                "name": "Webhook User",
                "organizations": [],
            }
        )
        mock_session_svc = MagicMock()
        mock_user_svc = AsyncMock()
        mock_user_svc.get_or_create_user.return_value = {
            "user_id": "uuid-1",
            "email": "webhook@example.com",
        }

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        ts = str(int(time.time()))
        event_type = "user"
        uuids = ["uuid-1"]
        secret = "test-webhook-secret"

        message = ts + event_type + "".join(uuids)
        sig = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        mock_settings = MagicMock()
        mock_settings.muckrock_client_secret = secret

        with patch("app.routers.auth.get_settings", return_value=mock_settings):
            response = client.post(
                "/api/auth/webhook",
                json={
                    "timestamp": ts,
                    "type": event_type,
                    "uuids": uuids,
                    "signature": sig,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed"] == 1
        mock_muckrock.fetch_user_data.assert_called_once_with("uuid-1")
        mock_user_svc.get_or_create_user.assert_called_once()

    def test_webhook_valid_org_event_individual_updates_user(self):
        """Org webhook for individual org should update user tier."""
        org_uuid = "user-uuid-1"
        mock_muckrock = MagicMock()
        mock_muckrock.fetch_org_data = AsyncMock(return_value={
            "uuid": org_uuid,
            "name": "User Org",
            "individual": True,
            "entitlements": [
                {"name": "cojournalist-pro", "resources": {"monthly_credits": 1000}, "update_on": "2026-04-01"}
            ],
        })
        mock_session_svc = MagicMock()
        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = {
            "user_id": org_uuid,
            "tier": "free",
            "credits": 50,
        }

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        ts = str(int(time.time()))
        event_type = "organization"
        uuids = [org_uuid]
        secret = "test-webhook-secret"

        message = ts + event_type + "".join(uuids)
        sig = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        mock_settings = MagicMock()
        mock_settings.muckrock_client_secret = secret

        with patch("app.routers.auth.get_settings", return_value=mock_settings):
            response = client.post(
                "/api/auth/webhook",
                json={
                    "timestamp": ts,
                    "type": event_type,
                    "uuids": uuids,
                    "signature": sig,
                },
            )
        assert response.status_code == 200
        mock_user_svc.update_tier_from_org.assert_called_once()

    def test_webhook_org_event_non_individual_skips(self):
        """Org webhook for non-individual (team) org should log and skip."""
        mock_muckrock = MagicMock()
        mock_muckrock.fetch_org_data = AsyncMock(return_value={
            "uuid": "team-org-uuid",
            "name": "News Team",
            "individual": False,
            "entitlements": [],
        })
        mock_session_svc = MagicMock()
        mock_user_svc = AsyncMock()

        auth_module._muckrock_client = mock_muckrock
        auth_module._session_service = mock_session_svc
        auth_module._user_service = mock_user_svc

        ts = str(int(time.time()))
        event_type = "organization"
        uuids = ["team-org-uuid"]
        secret = "test-webhook-secret"

        message = ts + event_type + "".join(uuids)
        sig = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        mock_settings = MagicMock()
        mock_settings.muckrock_client_secret = secret

        with patch("app.routers.auth.get_settings", return_value=mock_settings):
            response = client.post(
                "/api/auth/webhook",
                json={
                    "timestamp": ts,
                    "type": event_type,
                    "uuids": uuids,
                    "signature": sig,
                },
            )
        assert response.status_code == 200
        mock_user_svc.update_tier_from_org.assert_not_called()
