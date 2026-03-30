"""
Unit tests for LicenseKeyService and license router handlers.

Tests cover:
- License creation (dual DynamoDB records)
- License validation (valid key, invalid key, last_validated_at update)
- Subscription lookup (pointer record -> license record)
- License update (field updates)
- License revocation
- _generate_license_key() format and entropy
- Webhook handler functions (_handle_new_purchase, _handle_renewal,
  _handle_cancellation, _handle_payment_failed)
"""
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from app.services.license_key_service import LicenseKeyService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    """Mock DynamoDB table."""
    return MagicMock()


@pytest.fixture
def license_service(mock_table):
    """LicenseKeyService with mocked DynamoDB table."""
    with patch("app.services.license_key_service.get_settings") as mock_settings, \
         patch("app.services.license_key_service.boto3") as mock_boto:
        mock_settings.return_value.aws_region = "eu-central-1"
        mock_boto.resource.return_value.Table.return_value = mock_table
        service = LicenseKeyService()
    return service


# ---------------------------------------------------------------------------
# create_license()
# ---------------------------------------------------------------------------

class TestCreateLicense:
    def test_creates_two_dynamodb_records(self, license_service, mock_table):
        """create_license writes both LICENSE# and STRIPE_SUB# records."""
        license_service.create_license(
            key_hash="abc123hash",
            key_prefix="cjl_a8Kx2mNp",
            subscription_id="sub_1234",
            customer_id="cus_5678",
            customer_email="editor@newsroom.org",
            expires_at="2027-03-29T00:00:00+00:00",
        )

        assert mock_table.put_item.call_count == 2

        # First call: LICENSE# lookup record
        call1 = mock_table.put_item.call_args_list[0]
        item1 = call1.kwargs["Item"]
        assert item1["PK"] == "LICENSE#abc123hash"
        assert item1["SK"] == "META"
        assert item1["key_prefix"] == "cjl_a8Kx2mNp"
        assert item1["subscription_id"] == "sub_1234"
        assert item1["customer_id"] == "cus_5678"
        assert item1["customer_email"] == "editor@newsroom.org"
        assert item1["status"] == "active"
        assert item1["expires_at"] == "2027-03-29T00:00:00+00:00"
        assert "created_at" in item1
        assert item1["last_validated_at"] is None

        # Second call: STRIPE_SUB# pointer record
        call2 = mock_table.put_item.call_args_list[1]
        item2 = call2.kwargs["Item"]
        assert item2["PK"] == "STRIPE_SUB#sub_1234"
        assert item2["SK"] == "LICENSE"
        assert item2["key_hash"] == "abc123hash"


# ---------------------------------------------------------------------------
# validate_key()
# ---------------------------------------------------------------------------

class TestValidateKey:
    def test_returns_record_for_valid_key(self, license_service, mock_table):
        """validate_key returns the LICENSE# record when key exists."""
        raw_key = "cjl_testkey1-testkey2-testkey3-testkey4"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"LICENSE#{key_hash}",
                "SK": "META",
                "status": "active",
                "expires_at": "2027-03-29T00:00:00+00:00",
                "customer_email": "editor@newsroom.org",
            }
        }

        result = license_service.validate_key(raw_key)

        assert result is not None
        assert result["status"] == "active"
        assert result["customer_email"] == "editor@newsroom.org"

        # Verify it looked up by hash
        mock_table.get_item.assert_called_once_with(
            Key={"PK": f"LICENSE#{key_hash}", "SK": "META"}
        )

    def test_returns_none_for_invalid_key(self, license_service, mock_table):
        """validate_key returns None when key does not exist."""
        mock_table.get_item.return_value = {}

        result = license_service.validate_key("cjl_invalid-key-here-nope")
        assert result is None

    def test_updates_last_validated_at(self, license_service, mock_table):
        """validate_key updates last_validated_at timestamp on valid key."""
        raw_key = "cjl_testkey1-testkey2-testkey3-testkey4"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"LICENSE#{key_hash}",
                "SK": "META",
                "status": "active",
            }
        }

        license_service.validate_key(raw_key)

        # Verify update_item was called to update last_validated_at
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args.kwargs
        assert call_kwargs["Key"] == {"PK": f"LICENSE#{key_hash}", "SK": "META"}
        assert "last_validated_at" in call_kwargs["UpdateExpression"]

    def test_validation_succeeds_even_if_timestamp_update_fails(self, license_service, mock_table):
        """validate_key still returns the record if last_validated_at update throws."""
        raw_key = "cjl_testkey1-testkey2-testkey3-testkey4"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_table.get_item.return_value = {
            "Item": {"PK": f"LICENSE#{key_hash}", "SK": "META", "status": "active"}
        }
        mock_table.update_item.side_effect = Exception("DynamoDB throttled")

        result = license_service.validate_key(raw_key)
        assert result is not None
        assert result["status"] == "active"


# ---------------------------------------------------------------------------
# get_by_subscription()
# ---------------------------------------------------------------------------

class TestGetBySubscription:
    def test_follows_pointer_to_license_record(self, license_service, mock_table):
        """get_by_subscription reads pointer, then fetches license record."""
        mock_table.get_item.side_effect = [
            # First call: STRIPE_SUB# pointer
            {"Item": {"PK": "STRIPE_SUB#sub_1234", "SK": "LICENSE", "key_hash": "abc123hash"}},
            # Second call: LICENSE# record
            {"Item": {
                "PK": "LICENSE#abc123hash",
                "SK": "META",
                "status": "active",
                "customer_email": "editor@newsroom.org",
                "key_hash": "abc123hash",
            }},
        ]

        result = license_service.get_by_subscription("sub_1234")

        assert result is not None
        assert result["status"] == "active"
        assert result["customer_email"] == "editor@newsroom.org"
        assert mock_table.get_item.call_count == 2

    def test_returns_none_when_no_pointer(self, license_service, mock_table):
        """get_by_subscription returns None when subscription has no pointer."""
        mock_table.get_item.return_value = {}

        result = license_service.get_by_subscription("sub_unknown")
        assert result is None


# ---------------------------------------------------------------------------
# update_license()
# ---------------------------------------------------------------------------

class TestUpdateLicense:
    def test_updates_single_field(self, license_service, mock_table):
        """update_license builds correct UpdateExpression for one field."""
        license_service.update_license("abc123hash", {"status": "cancelled"})

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args.kwargs
        assert call_kwargs["Key"] == {"PK": "LICENSE#abc123hash", "SK": "META"}
        assert "#status = :val0" in call_kwargs["UpdateExpression"]
        assert call_kwargs["ExpressionAttributeValues"][":val0"] == "cancelled"
        assert call_kwargs["ExpressionAttributeNames"]["#status"] == "status"

    def test_updates_multiple_fields(self, license_service, mock_table):
        """update_license handles multiple field updates."""
        license_service.update_license(
            "abc123hash",
            {"status": "cancelled", "expires_at": "2027-06-01T00:00:00+00:00"},
        )

        call_kwargs = mock_table.update_item.call_args.kwargs
        assert ":val0" in call_kwargs["ExpressionAttributeValues"]
        assert ":val1" in call_kwargs["ExpressionAttributeValues"]


# ---------------------------------------------------------------------------
# revoke_license()
# ---------------------------------------------------------------------------

class TestRevokeLicense:
    def test_sets_status_to_revoked(self, license_service, mock_table):
        """revoke_license calls update_license with status=revoked."""
        license_service.revoke_license("abc123hash")

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args.kwargs
        assert call_kwargs["ExpressionAttributeValues"][":val0"] == "revoked"


# ---------------------------------------------------------------------------
# Router tests (license.py endpoints)
# ---------------------------------------------------------------------------

from app.routers.license import (
    _generate_license_key,
    _handle_new_purchase,
    _handle_renewal,
    _handle_cancellation,
    _handle_payment_failed,
)


# ---------------------------------------------------------------------------
# _generate_license_key()
# ---------------------------------------------------------------------------

class TestGenerateLicenseKey:
    def test_key_starts_with_prefix(self):
        """Generated key starts with cjl_ prefix."""
        key = _generate_license_key()
        assert key.startswith("cjl_")

    def test_key_has_four_hyphen_separated_groups(self):
        """Generated key has format cjl_XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX."""
        key = _generate_license_key()
        # Remove prefix, split by hyphens
        parts = key[4:].split("-")
        assert len(parts) == 4

    def test_key_has_sufficient_length(self):
        """Generated key is ~39 chars total."""
        key = _generate_license_key()
        # "cjl_" (4) + 4 groups of 8 chars (32) + 3 hyphens (3) = 39
        assert len(key) >= 35  # Allow for base64url variance

    def test_keys_are_unique(self):
        """Two generated keys should not be equal."""
        key1 = _generate_license_key()
        key2 = _generate_license_key()
        assert key1 != key2


# ---------------------------------------------------------------------------
# _handle_new_purchase()
# ---------------------------------------------------------------------------

class TestHandleNewPurchase:
    @pytest.mark.asyncio
    async def test_creates_license_for_new_subscription(self):
        """New purchase creates a license via LicenseKeyService."""
        session = {
            "subscription": "sub_new_1234",
            "customer": "cus_5678",
            "customer_details": {"email": "editor@newsroom.org"},
        }

        with patch("app.routers.license.LicenseKeyService") as MockService, \
             patch("app.routers.license._send_license_email", new_callable=AsyncMock) as mock_email:
            mock_instance = MockService.return_value
            mock_instance.get_by_subscription.return_value = None  # No existing license

            await _handle_new_purchase(session)

            mock_instance.create_license.assert_called_once()
            call_kwargs = mock_instance.create_license.call_args.kwargs
            assert call_kwargs["subscription_id"] == "sub_new_1234"
            assert call_kwargs["customer_id"] == "cus_5678"
            assert call_kwargs["customer_email"] == "editor@newsroom.org"
            assert call_kwargs["key_prefix"].startswith("cjl_")
            assert len(call_kwargs["key_hash"]) == 64  # SHA-256 hex
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_if_license_already_exists(self):
        """Idempotency: skips creation if license already exists for subscription."""
        session = {
            "subscription": "sub_existing_1234",
            "customer": "cus_5678",
            "customer_details": {"email": "editor@newsroom.org"},
        }

        with patch("app.routers.license.LicenseKeyService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_by_subscription.return_value = {"status": "active"}

            await _handle_new_purchase(session)

            mock_instance.create_license.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_renewal()
# ---------------------------------------------------------------------------

class TestHandleRenewal:
    @pytest.mark.asyncio
    async def test_extends_expiry_by_one_year(self):
        """Renewal extends expires_at by 365 days from current expiry."""
        invoice = {"subscription": "sub_1234", "billing_reason": "subscription_cycle"}

        with patch("app.routers.license.LicenseKeyService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_by_subscription.return_value = {
                "key_hash": "abc123hash",
                "expires_at": "2027-03-29T00:00:00+00:00",
            }

            await _handle_renewal(invoice)

            mock_instance.update_license.assert_called_once()
            call_kwargs = mock_instance.update_license.call_args.kwargs
            assert call_kwargs["key_hash"] == "abc123hash"
            # New expiry should be ~2028-03-29
            assert "2028" in call_kwargs["updates"]["expires_at"]
            assert call_kwargs["updates"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_does_nothing_when_no_license_found(self):
        """Renewal is a no-op when no license exists for the subscription."""
        invoice = {"subscription": "sub_unknown"}

        with patch("app.routers.license.LicenseKeyService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_by_subscription.return_value = None

            await _handle_renewal(invoice)

            mock_instance.update_license.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_cancellation()
# ---------------------------------------------------------------------------

class TestHandleCancellation:
    @pytest.mark.asyncio
    async def test_sets_status_cancelled_and_expires_at_period_end(self):
        """Cancellation sets status=cancelled and expires_at to period end."""
        subscription = {
            "id": "sub_1234",
            "current_period_end": 1806537600,  # 2027-03-29 00:00:00 UTC
        }

        with patch("app.routers.license.LicenseKeyService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_by_subscription.return_value = {
                "key_hash": "abc123hash",
            }

            await _handle_cancellation(subscription)

            mock_instance.update_license.assert_called_once()
            call_kwargs = mock_instance.update_license.call_args.kwargs
            assert call_kwargs["key_hash"] == "abc123hash"
            assert call_kwargs["updates"]["status"] == "cancelled"
            assert "expires_at" in call_kwargs["updates"]


# ---------------------------------------------------------------------------
# _handle_payment_failed()
# ---------------------------------------------------------------------------

class TestHandlePaymentFailed:
    @pytest.mark.asyncio
    async def test_sets_status_past_due(self):
        """Payment failure sets status to past_due."""
        invoice = {"subscription": "sub_1234"}

        with patch("app.routers.license.LicenseKeyService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_by_subscription.return_value = {
                "key_hash": "abc123hash",
            }

            await _handle_payment_failed(invoice)

            mock_instance.update_license.assert_called_once()
            call_kwargs = mock_instance.update_license.call_args.kwargs
            assert call_kwargs["key_hash"] == "abc123hash"
            assert call_kwargs["updates"] == {"status": "past_due"}
