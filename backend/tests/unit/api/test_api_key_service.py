"""
Unit tests for ApiKeyService and verify_api_key dependency.

Tests cover:
- Key generation format and hash determinism
- Key creation with dual DynamoDB records
- Max keys per user enforcement
- Key listing
- Key revocation (valid + not found)
- Key validation (valid, invalid, revoked)
- verify_api_key dependency (missing header, wrong format, valid key, invalid key, user not found)
"""
import hashlib
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import HTTPException

from app.services.api_key_service import ApiKeyService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    """Mock DynamoDB table."""
    return MagicMock()


@pytest.fixture
def api_key_service(mock_table):
    """ApiKeyService with mocked DynamoDB table."""
    with patch("app.services.api_key_service.get_settings") as mock_settings, \
         patch("app.services.api_key_service.boto3") as mock_boto:
        mock_settings.return_value.aws_region = "eu-central-1"
        mock_boto.resource.return_value.Table.return_value = mock_table
        service = ApiKeyService()
    return service


# ---------------------------------------------------------------------------
# generate_key()
# ---------------------------------------------------------------------------

class TestGenerateKey:
    def test_key_format_starts_with_prefix(self, api_key_service):
        raw_key, key_hash = api_key_service.generate_key()
        assert raw_key.startswith("cj_")

    def test_key_is_sufficiently_long(self, api_key_service):
        raw_key, _ = api_key_service.generate_key()
        # "cj_" (3 chars) + token_urlsafe(32) (~43 chars)
        assert len(raw_key) > 40

    def test_hash_is_sha256_hex(self, api_key_service):
        raw_key, key_hash = api_key_service.generate_key()
        assert len(key_hash) == 64  # SHA-256 hex = 64 chars
        # Verify hash matches
        expected = hashlib.sha256(raw_key.encode()).hexdigest()
        assert key_hash == expected

    def test_hash_determinism(self, api_key_service):
        """Same raw key always produces the same hash when generate_key is called twice."""
        fixed_token = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        with patch("app.services.api_key_service.secrets.token_urlsafe", return_value=fixed_token):
            key1, hash1 = api_key_service.generate_key()
            key2, hash2 = api_key_service.generate_key()

        assert key1 == key2
        assert hash1 == hash2
        assert key1 == f"cj_{fixed_token}"
        assert hash1 == hashlib.sha256(key1.encode()).hexdigest()

    def test_keys_are_unique(self, api_key_service):
        key1, hash1 = api_key_service.generate_key()
        key2, hash2 = api_key_service.generate_key()
        assert key1 != key2
        assert hash1 != hash2


# ---------------------------------------------------------------------------
# create_key()
# ---------------------------------------------------------------------------

class TestCreateKey:
    def test_creates_both_records(self, api_key_service, mock_table):
        mock_table.query.return_value = {"Items": []}

        result = api_key_service.create_key("user-123", name="My Key")

        assert mock_table.put_item.call_count == 2
        calls = mock_table.put_item.call_args_list

        # Lookup record
        lookup = calls[0].kwargs["Item"]
        assert lookup["PK"].startswith("APIKEY#")
        assert lookup["SK"] == "META"
        assert lookup["user_id"] == "user-123"
        assert lookup["name"] == "My Key"

        # User listing record
        user_rec = calls[1].kwargs["Item"]
        assert user_rec["PK"] == "user-123"
        assert user_rec["SK"].startswith("APIKEY#")
        assert user_rec["name"] == "My Key"

    def test_returns_raw_key_shown_once(self, api_key_service, mock_table):
        mock_table.query.return_value = {"Items": []}

        result = api_key_service.create_key("user-123")

        assert "raw_key" in result
        assert result["raw_key"].startswith("cj_")
        assert "key_id" in result
        assert "key_prefix" in result
        assert "created_at" in result

    def test_key_prefix_is_first_seven_chars(self, api_key_service, mock_table):
        mock_table.query.return_value = {"Items": []}

        result = api_key_service.create_key("user-123")

        assert result["key_prefix"] == result["raw_key"][:7]

    def test_default_empty_name(self, api_key_service, mock_table):
        mock_table.query.return_value = {"Items": []}

        result = api_key_service.create_key("user-123")

        assert result["name"] == ""

    def test_max_keys_enforcement(self, api_key_service, mock_table):
        existing_items = [
            {"SK": f"APIKEY#key-{i}", "key_prefix": "cj_xxx", "name": "", "created_at": ""}
            for i in range(5)
        ]
        mock_table.query.return_value = {"Items": existing_items}

        with pytest.raises(ValueError, match="Maximum of 5"):
            api_key_service.create_key("user-123")

        mock_table.put_item.assert_not_called()

    def test_allows_key_below_max(self, api_key_service, mock_table):
        existing_items = [
            {"SK": f"APIKEY#key-{i}", "key_prefix": "cj_xxx", "name": "", "created_at": ""}
            for i in range(4)
        ]
        mock_table.query.return_value = {"Items": existing_items}

        result = api_key_service.create_key("user-123")

        assert result["raw_key"].startswith("cj_")
        assert mock_table.put_item.call_count == 2


# ---------------------------------------------------------------------------
# list_keys()
# ---------------------------------------------------------------------------

class TestListKeys:
    def test_returns_key_metadata(self, api_key_service, mock_table):
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "user-123",
                    "SK": "APIKEY#key-abc",
                    "key_prefix": "cj_Abc1",
                    "name": "Production",
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "PK": "user-123",
                    "SK": "APIKEY#key-def",
                    "key_prefix": "cj_Def2",
                    "name": "Staging",
                    "created_at": "2026-01-02T00:00:00+00:00",
                },
            ]
        }

        keys = api_key_service.list_keys("user-123")

        assert len(keys) == 2
        assert keys[0]["key_id"] == "key-abc"
        assert keys[0]["key_prefix"] == "cj_Abc1"
        assert keys[0]["name"] == "Production"
        assert keys[1]["key_id"] == "key-def"

    def test_returns_empty_for_no_keys(self, api_key_service, mock_table):
        mock_table.query.return_value = {"Items": []}

        keys = api_key_service.list_keys("user-123")

        assert keys == []

    def test_does_not_return_raw_keys(self, api_key_service, mock_table):
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "user-123",
                    "SK": "APIKEY#key-abc",
                    "key_prefix": "cj_Abc1",
                    "key_hash": "abc123hash",
                    "name": "",
                    "created_at": "",
                },
            ]
        }

        keys = api_key_service.list_keys("user-123")

        assert "raw_key" not in keys[0]
        assert "key_hash" not in keys[0]


# ---------------------------------------------------------------------------
# revoke_key()
# ---------------------------------------------------------------------------

class TestRevokeKey:
    def test_revoke_existing_key(self, api_key_service, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "user-123",
                "SK": "APIKEY#key-abc",
                "key_hash": "hash123",
                "key_prefix": "cj_Abc1",
                "name": "My Key",
            }
        }

        result = api_key_service.revoke_key("user-123", "key-abc")

        assert result is True
        assert mock_table.delete_item.call_count == 2

        # Verify both records deleted
        calls = mock_table.delete_item.call_args_list
        lookup_key = calls[0].kwargs["Key"]
        assert lookup_key == {"PK": "APIKEY#hash123", "SK": "META"}

        user_key = calls[1].kwargs["Key"]
        assert user_key == {"PK": "user-123", "SK": "APIKEY#key-abc"}

    def test_revoke_nonexistent_key(self, api_key_service, mock_table):
        mock_table.get_item.return_value = {}

        result = api_key_service.revoke_key("user-123", "nonexistent")

        assert result is False
        mock_table.delete_item.assert_not_called()

    def test_revoke_checks_ownership(self, api_key_service, mock_table):
        """Revoke looks up user's own listing record, not a different user's."""
        mock_table.get_item.return_value = {}

        result = api_key_service.revoke_key("user-456", "key-from-user-123")

        assert result is False
        # Verify it queried the correct user
        mock_table.get_item.assert_called_once_with(
            Key={"PK": "user-456", "SK": "APIKEY#key-from-user-123"}
        )


# ---------------------------------------------------------------------------
# validate_key()
# ---------------------------------------------------------------------------

class TestValidateKey:
    def test_valid_key_returns_user_id(self, api_key_service, mock_table):
        raw_key = "cj_test_valid_key_abc123"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"APIKEY#{key_hash}",
                "SK": "META",
                "user_id": "user-123",
            }
        }

        result = api_key_service.validate_key(raw_key)

        assert result == "user-123"

    def test_valid_key_updates_last_used(self, api_key_service, mock_table):
        raw_key = "cj_test_valid_key_abc123"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"APIKEY#{key_hash}",
                "SK": "META",
                "user_id": "user-123",
            }
        }

        api_key_service.validate_key(raw_key)

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args.kwargs
        assert call_kwargs["Key"] == {"PK": f"APIKEY#{key_hash}", "SK": "META"}
        assert "last_used_at" in call_kwargs["UpdateExpression"]

    def test_invalid_key_returns_none(self, api_key_service, mock_table):
        mock_table.get_item.return_value = {}

        result = api_key_service.validate_key("cj_nonexistent_key")

        assert result is None
        mock_table.update_item.assert_not_called()

    def test_revoked_key_returns_none(self, api_key_service, mock_table):
        """After revocation, the lookup record is deleted so validation fails."""
        mock_table.get_item.return_value = {}

        result = api_key_service.validate_key("cj_was_revoked_key")

        assert result is None


# ---------------------------------------------------------------------------
# verify_api_key() dependency
# ---------------------------------------------------------------------------

class TestVerifyApiKeyDependency:
    @pytest.mark.asyncio
    async def test_missing_auth_header(self):
        from app.dependencies import verify_api_key

        request = MagicMock()
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 401
        assert "Missing or invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_prefix(self):
        from app.dependencies import verify_api_key

        request = MagicMock()
        request.headers = {"Authorization": "Bearer sk_wrong_prefix"}

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 401
        assert "Missing or invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_bearer(self):
        from app.dependencies import verify_api_key

        request = MagicMock()
        request.headers = {"Authorization": "Bearer "}

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_key(self):
        from app.dependencies import verify_api_key

        request = MagicMock()
        request.headers = {"Authorization": "Bearer cj_invalid_key_12345"}

        mock_api_svc = MagicMock()
        mock_api_svc.validate_key.return_value = None

        with patch("app.dependencies.auth._get_api_key_service", return_value=mock_api_svc):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(request)
            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_key_returns_user_with_needs_initialization(self):
        from app.dependencies import verify_api_key

        request = MagicMock()
        request.headers = {"Authorization": "Bearer cj_valid_key_12345"}

        # get_user() returns raw profile — no needs_initialization field
        mock_user_from_db = {
            "user_id": "user-123",
            "muckrock_id": "user-123",
            "tier": "pro",
            "credits": 100,
            "timezone": "UTC",
            "preferred_language": "en",
            "onboarding_completed": True,
            "default_location": None,
            "excluded_domains": [],
            "cms_api_url": None,
            "has_cms_token": False,
        }

        mock_api_svc = MagicMock()
        mock_api_svc.validate_key.return_value = "user-123"

        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = mock_user_from_db

        mock_session_svc = MagicMock()

        with patch("app.dependencies.auth._get_api_key_service", return_value=mock_api_svc), \
             patch("app.dependencies.auth._get_services", return_value=(mock_session_svc, mock_user_svc)):
            result = await verify_api_key(request)

        assert result["user_id"] == "user-123"
        assert result["tier"] == "pro"
        # build_user_response computes needs_initialization
        assert "needs_initialization" in result
        assert result["needs_initialization"] is False
        mock_api_svc.validate_key.assert_called_once_with("cj_valid_key_12345")
        mock_user_svc.get_user.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_valid_key_but_user_not_found(self):
        from app.dependencies import verify_api_key

        request = MagicMock()
        request.headers = {"Authorization": "Bearer cj_orphaned_key_12345"}

        mock_api_svc = MagicMock()
        mock_api_svc.validate_key.return_value = "deleted-user"

        mock_user_svc = AsyncMock()
        mock_user_svc.get_user.return_value = None

        mock_session_svc = MagicMock()

        with patch("app.dependencies.auth._get_api_key_service", return_value=mock_api_svc), \
             patch("app.dependencies.auth._get_services", return_value=(mock_session_svc, mock_user_svc)):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(request)
            assert exc_info.value.status_code == 401
            assert "User not found" in exc_info.value.detail
