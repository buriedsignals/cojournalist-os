"""
License key management for gating automation scripts.

PURPOSE: Manages LICENSE# and STRIPE_SUB# records in the scraping-jobs table
(single-table design). Handles license creation, validation, subscription
lookup, updates, and revocation.

DEPENDS ON: config (AWS region), boto3 (DynamoDB)
USED BY: routers/license.py (validation endpoint + webhook handler)

Records in scraping-jobs table:
- LICENSE#<sha256(key)> / META          -- key_prefix, subscription_id, status, expires_at
- STRIPE_SUB#<subscription_id> / LICENSE -- key_hash (pointer to LICENSE# record)
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3

from app.config import get_settings

logger = logging.getLogger(__name__)


class LicenseKeyService:
    TABLE_NAME = "scraping-jobs"

    def __init__(self):
        settings = get_settings()
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.table = self.dynamodb.Table(self.TABLE_NAME)

    def create_license(
        self,
        key_hash: str,
        key_prefix: str,
        subscription_id: str,
        customer_id: str,
        customer_email: str,
        expires_at: str,
    ) -> None:
        """Create a new license key record pair.

        Writes two DynamoDB records:
        1. LICENSE#{hash} / META - the license record (for validation)
        2. STRIPE_SUB#{sub_id} / LICENSE - pointer (for webhook handlers)
        """
        now = datetime.now(timezone.utc).isoformat()

        # Lookup record (for validation endpoint)
        self.table.put_item(Item={
            "PK": f"LICENSE#{key_hash}",
            "SK": "META",
            "key_prefix": key_prefix,
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "customer_email": customer_email,
            "status": "active",
            "expires_at": expires_at,
            "created_at": now,
            "last_validated_at": None,
        })

        # Subscription pointer (for webhook handlers)
        self.table.put_item(Item={
            "PK": f"STRIPE_SUB#{subscription_id}",
            "SK": "LICENSE",
            "key_hash": key_hash,
        })

        logger.info(f"Created license {key_prefix}... for {customer_email}")

    def validate_key(self, raw_key: str) -> Optional[dict]:
        """Validate a license key. Returns license record or None.

        Also updates last_validated_at timestamp (fire-and-forget).
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        response = self.table.get_item(
            Key={"PK": f"LICENSE#{key_hash}", "SK": "META"}
        )
        item = response.get("Item")
        if not item:
            return None

        # Update last_validated_at (fire-and-forget, don't block on this)
        now = datetime.now(timezone.utc).isoformat()
        try:
            self.table.update_item(
                Key={"PK": f"LICENSE#{key_hash}", "SK": "META"},
                UpdateExpression="SET last_validated_at = :now",
                ExpressionAttributeValues={":now": now},
            )
        except Exception:
            pass  # Non-critical -- don't fail validation over a timestamp update

        return item

    def get_by_subscription(self, subscription_id: str) -> Optional[dict]:
        """Look up a license by Stripe subscription ID.

        Reads the STRIPE_SUB# pointer record, then fetches the LICENSE# record.
        """
        # Get the pointer record
        pointer = self.table.get_item(
            Key={"PK": f"STRIPE_SUB#{subscription_id}", "SK": "LICENSE"}
        ).get("Item")

        if not pointer:
            return None

        key_hash = pointer["key_hash"]

        # Get the actual license record
        return self.table.get_item(
            Key={"PK": f"LICENSE#{key_hash}", "SK": "META"}
        ).get("Item")

    def update_license(self, key_hash: str, updates: dict) -> None:
        """Update fields on a license record.

        Args:
            key_hash: SHA-256 hash of the license key.
            updates: Dict of field names to new values (e.g. {"status": "cancelled"}).
        """
        expressions = []
        values = {}
        for i, (field, value) in enumerate(updates.items()):
            expressions.append(f"#{field} = :val{i}")
            values[f":val{i}"] = value

        names = {f"#{field}": field for field in updates}

        self.table.update_item(
            Key={"PK": f"LICENSE#{key_hash}", "SK": "META"},
            UpdateExpression="SET " + ", ".join(expressions),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def revoke_license(self, key_hash: str) -> None:
        """Admin: manually revoke a license."""
        self.update_license(key_hash, {"status": "revoked"})
