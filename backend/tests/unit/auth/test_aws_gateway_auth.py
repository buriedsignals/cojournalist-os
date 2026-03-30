# backend/tests/unit/auth/test_aws_gateway_auth.py
"""
Unit tests for the HMAC-signed AWS API Gateway headers.

Tests verify:
1. Correct header keys are generated
2. HMAC signature is valid and verifiable
3. Tampered user_id invalidates signature
4. Tampered timezone invalidates signature
5. Expired timestamps are detectable
"""
import hashlib
import hmac
import time
from typing import Optional
from unittest.mock import patch

import pytest


# --- Helper to verify signatures (mirrors what the Lambda authorizer does) ---

def verify_signature(headers: dict, service_key: str, max_age: int = 300) -> Optional[dict]:
    """Verify HMAC-signed headers. Returns {"user_id": ..., "timezone": ...} or None."""
    try:
        user_id = headers["X-User-Id"]
        timezone = headers["X-User-Timezone"]
        timestamp = headers["X-Timestamp"]
        signature = headers["X-Signature"]
        key = headers["X-Service-Key"]
    except KeyError:
        return None

    # Check service key
    if not hmac.compare_digest(key, service_key):
        return None

    # Check timestamp freshness
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return None
    if abs(time.time() - ts) > max_age:
        return None

    # Verify HMAC
    message = f"{user_id}:{timezone}:{timestamp}"
    expected = hmac.new(service_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    return {"user_id": user_id, "timezone": timezone}


class TestBuildAwsHeaders:
    """Tests for _build_aws_headers in scraper.py."""

    def _build_headers(self, user: dict) -> dict:
        """Import and call _build_aws_headers."""
        from app.routers.scraper import _build_aws_headers
        return _build_aws_headers(user)

    @patch("app.routers.scraper.settings")
    def test_returns_all_required_keys(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "abc-123", "timezone": "Europe/Zurich"}
        headers = self._build_headers(user)

        assert "X-Service-Key" in headers
        assert "X-User-Id" in headers
        assert "X-User-Timezone" in headers
        assert "X-Timestamp" in headers
        assert "X-Signature" in headers
        assert headers["Content-Type"] == "application/json"

    @patch("app.routers.scraper.settings")
    def test_signature_is_verifiable(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "abc-123", "timezone": "Europe/Zurich"}
        headers = self._build_headers(user)

        result = verify_signature(headers, "test-key-12345")
        assert result is not None
        assert result["user_id"] == "abc-123"
        assert result["timezone"] == "Europe/Zurich"

    @patch("app.routers.scraper.settings")
    def test_tampered_user_id_fails_verification(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "abc-123", "timezone": "UTC"}
        headers = self._build_headers(user)

        headers["X-User-Id"] = "evil-user-456"
        result = verify_signature(headers, "test-key-12345")
        assert result is None

    @patch("app.routers.scraper.settings")
    def test_tampered_timezone_fails_verification(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "abc-123", "timezone": "Europe/Zurich"}
        headers = self._build_headers(user)

        headers["X-User-Timezone"] = "America/New_York"
        result = verify_signature(headers, "test-key-12345")
        assert result is None

    @patch("app.routers.scraper.settings")
    def test_wrong_service_key_fails_verification(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "abc-123", "timezone": "UTC"}
        headers = self._build_headers(user)

        result = verify_signature(headers, "wrong-key")
        assert result is None

    def test_expired_timestamp_fails_verification(self):
        """Construct a validly-signed request with an old timestamp to test expiry."""
        service_key = "test-key-12345"
        user_id = "abc-123"
        timezone = "UTC"
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago

        # Sign correctly with the old timestamp
        message = f"{user_id}:{timezone}:{old_timestamp}"
        signature = hmac.new(service_key.encode(), message.encode(), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Service-Key": service_key,
            "X-User-Id": user_id,
            "X-User-Timezone": timezone,
            "X-Timestamp": old_timestamp,
            "X-Signature": signature,
        }

        # HMAC is valid, but timestamp is expired
        result = verify_signature(headers, service_key, max_age=300)
        assert result is None

    @patch("app.routers.scraper.settings")
    def test_null_timezone_defaults_to_utc(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "abc-123", "timezone": None}
        headers = self._build_headers(user)

        assert headers["X-User-Timezone"] == "UTC"
        result = verify_signature(headers, "test-key-12345")
        assert result is not None
        assert result["timezone"] == "UTC"

    @patch("app.routers.scraper.settings")
    def test_user_id_in_header_matches_input(self, mock_settings):
        mock_settings.internal_service_key = "test-key-12345"
        user = {"user_id": "muckrock-uuid-here", "timezone": "US/Eastern"}
        headers = self._build_headers(user)

        assert headers["X-User-Id"] == "muckrock-uuid-here"
        assert headers["X-User-Timezone"] == "US/Eastern"
