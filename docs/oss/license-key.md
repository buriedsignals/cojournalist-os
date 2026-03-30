# License Key Infrastructure Design

License keys gate the automation scripts (`setup.sh`, `sync-upstream.yml` GitHub Action) — not application features. Customers buy an annual license via Stripe Checkout. Stripe webhooks generate and manage the key lifecycle.

## Architecture Overview

```
Stripe Checkout → webhook → FastAPI → generate license key → DynamoDB
                                                            ↓
setup.sh / sync-upstream.yml → POST /api/license/validate (key in body) → 200/403
```

**Principle:** Keep it minimal. One DynamoDB record type, one webhook handler, one validation endpoint. No separate database.

---

## 1. Stripe Integration

### Checkout Session Setup

Create a Stripe Product with an annual Price. The Checkout Session embeds `client_reference_id` (optional — for linking to an existing coJournalist user) and uses `subscription_data.metadata` to tag the subscription:

```python
session = stripe.checkout.Session.create(
    mode="subscription",
    line_items=[{"price": ANNUAL_PRICE_ID, "quantity": 1}],
    success_url="https://www.cojournalist.ai/license/success?session_id={CHECKOUT_SESSION_ID}",
    cancel_url="https://www.cojournalist.ai/license/cancel",
    subscription_data={
        "metadata": {"product": "cojournalist-license"}
    },
    # Optional: pre-fill customer email
    customer_email=customer_email,
)
```

### Webhook Events to Handle

| Event | When it fires | Action |
|-------|--------------|--------|
| `checkout.session.completed` | First purchase completes | Generate license key, store LICENSE# record, email key to customer |
| `invoice.paid` | Annual renewal succeeds (`billing_reason: subscription_cycle`) | Extend `expires_at` by 1 year |
| `customer.subscription.deleted` | Subscription cancelled (end of period) | Set `status: cancelled`, set `expires_at` to period end |
| `invoice.payment_failed` | Renewal payment fails | Set `status: past_due` (key still works until `expires_at`) |

**Events NOT needed:**
- `customer.subscription.updated` — too noisy, fires on every metadata change
- `customer.subscription.created` — redundant with `checkout.session.completed`

### Webhook Handler

```python
# backend/app/routers/license.py

import stripe
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.post("/license/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for license key management."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    settings = get_settings()

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_new_purchase(data)

    elif event_type == "invoice.paid":
        invoice = data
        if invoice.get("billing_reason") == "subscription_cycle":
            await _handle_renewal(invoice)

    elif event_type == "customer.subscription.deleted":
        await _handle_cancellation(data)

    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data)

    return {"status": "ok"}


async def _handle_new_purchase(session: dict):
    """Generate license key on first purchase."""
    subscription_id = session.get("subscription")

    # Idempotency: check if license already exists for this subscription
    # (Stripe can redeliver webhooks; without this check, each delivery
    # would generate a new key and orphan the previous one)
    service = LicenseKeyService()
    existing = service.get_by_subscription(subscription_id)
    if existing:
        logger.info(f"License already exists for subscription {subscription_id}, skipping")
        return

    customer_id = session.get("customer")
    customer_email = session.get("customer_details", {}).get("email")

    # Generate key
    license_key = _generate_license_key()
    key_hash = hashlib.sha256(license_key.encode()).hexdigest()

    # Calculate expiry (1 year from now)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=365)).isoformat()

    # Store in DynamoDB (reuse service from idempotency check above)
    service.create_license(
        key_hash=key_hash,
        key_prefix=license_key[:12],  # "cjl_" + 8 chars
        subscription_id=subscription_id,
        customer_id=customer_id,
        customer_email=customer_email,
        expires_at=expires_at,
    )

    # Email the key to the customer
    await _send_license_email(customer_email, license_key)


async def _handle_renewal(invoice: dict):
    """Extend license expiry on successful annual renewal."""
    subscription_id = invoice.get("subscription")
    service = LicenseKeyService()

    # Look up license by subscription_id (GSI query)
    license_record = service.get_by_subscription(subscription_id)
    if not license_record:
        logger.warning(f"No license found for subscription {subscription_id}")
        return

    # Extend by 1 year from current expiry (not from now — avoids drift)
    current_expiry = datetime.fromisoformat(license_record["expires_at"])
    new_expiry = (current_expiry + timedelta(days=365)).isoformat()

    service.update_license(
        key_hash=license_record["key_hash"],
        updates={"expires_at": new_expiry, "status": "active"},
    )


async def _handle_cancellation(subscription: dict):
    """Mark license as cancelled (still valid until expires_at)."""
    subscription_id = subscription.get("id")
    # current_period_end is when access actually ends
    period_end = subscription.get("current_period_end")

    service = LicenseKeyService()
    license_record = service.get_by_subscription(subscription_id)
    if not license_record:
        return

    expires_at = datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat()

    service.update_license(
        key_hash=license_record["key_hash"],
        updates={"status": "cancelled", "expires_at": expires_at},
    )


async def _handle_payment_failed(invoice: dict):
    """Mark license as past_due (still works until expires_at)."""
    subscription_id = invoice.get("subscription")
    service = LicenseKeyService()
    license_record = service.get_by_subscription(subscription_id)
    if not license_record:
        return

    service.update_license(
        key_hash=license_record["key_hash"],
        updates={"status": "past_due"},
    )
```

---

## 2. License Key Format & Generation

```python
import secrets

def _generate_license_key() -> str:
    """Generate a license key.

    Format: cjl_XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
    - Prefix: cjl_ (coJournalist License)
    - 4 groups of 8 alphanumeric chars separated by hyphens
    - ~192 bits of entropy (token_urlsafe generates base64url chars)
    - Total length: 39 chars

    The key is shown to the user ONCE (at purchase) and emailed.
    Only the SHA-256 hash is stored.
    """
    parts = [secrets.token_urlsafe(6) for _ in range(4)]  # 6 bytes = 8 base64 chars each
    return "cjl_" + "-".join(parts)
```

**Example key:** `cjl_a8Kx2mNp-Qr7bYw3j-Hn5cTvLd-Ws9fPgE4`

**Why this format:**
- `cjl_` prefix makes it obvious what the key is for (grep-friendly, like `cj_` for API keys)
- Hyphens make it easy to read and paste (vs one long string)
- 192 bits of entropy makes brute force impossible
- Only the SHA-256 hash is stored in DynamoDB (same pattern as `api_key_service.py`)

---

## 3. DynamoDB Record Structure

Uses the existing `scraping-jobs` table (single-table design). Two record patterns:

### Lookup Record (hash-based O(1) validation)

```
PK: LICENSE#{sha256(key)}
SK: META
```

| Field | Type | Description |
|-------|------|-------------|
| key_prefix | string | First 12 chars of key (e.g., `cjl_a8Kx2mNp`) for admin display |
| subscription_id | string | Stripe subscription ID (e.g., `sub_1234`) |
| customer_id | string | Stripe customer ID (e.g., `cus_1234`) |
| customer_email | string | Email at time of purchase |
| status | string | `active`, `past_due`, `cancelled`, `revoked` |
| expires_at | string | ISO timestamp — when access ends |
| created_at | string | ISO timestamp |
| last_validated_at | string | ISO timestamp — last successful validation |

### Subscription Lookup Record (for webhook handlers)

```
PK: STRIPE_SUB#{subscription_id}
SK: LICENSE
```

| Field | Type | Description |
|-------|------|-------------|
| key_hash | string | SHA-256 hash of license key (pointer to lookup record) |

**Why two records instead of a GSI?**

A second record is cheaper and simpler than adding a GSI to the table. Webhooks use `subscription_id` to find the license; validation uses the `key_hash`. Two access patterns, two records. Follows the same dual-record pattern already used by `api_key_service.py` (APIKEY# lookup + user listing).

### Service Implementation

```python
# backend/app/services/license_key_service.py

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
        """Create a new license key record pair."""
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

        Also updates last_validated_at timestamp.
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
            pass  # Non-critical — don't fail validation over a timestamp update

        return item

    def get_by_subscription(self, subscription_id: str) -> Optional[dict]:
        """Look up a license by Stripe subscription ID."""
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
        """Update fields on a license record."""
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
```

---

## 4. Validation Endpoint

```python
# In backend/app/routers/license.py

from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse

@router.post("/license/validate")
async def validate_license(request: Request):
    """Validate a license key.

    Accepts JSON body: {"key": "cjl_..."}

    Returns:
        200 with metadata if valid and not expired.
        403 if invalid, expired, or revoked.

    No authentication required — the key IS the credential.
    Rate limited to prevent brute force.
    """
    body = await request.json()
    key = body.get("key", "")
    service = LicenseKeyService()
    record = service.validate_key(key)

    if not record:
        return JSONResponse(
            status_code=403,
            content={"valid": False, "error": "Invalid license key"},
        )

    # Check expiry
    expires_at = datetime.fromisoformat(record["expires_at"])
    now = datetime.now(timezone.utc)

    if now > expires_at:
        return JSONResponse(
            status_code=403,
            content={
                "valid": False,
                "error": "License expired",
                "expired_at": record["expires_at"],
            },
        )

    # Check status
    status = record.get("status", "active")
    if status == "revoked":
        return JSONResponse(
            status_code=403,
            content={"valid": False, "error": "License revoked"},
        )

    # Valid — return metadata (useful for setup.sh to display)
    return {
        "valid": True,
        "status": status,  # "active", "past_due", "cancelled"
        "expires_at": record["expires_at"],
        "customer_email": record.get("customer_email"),
    }
```

### What the endpoint returns

| Scenario | HTTP | Body |
|----------|------|------|
| Valid + active | 200 | `{"valid": true, "status": "active", "expires_at": "...", "customer_email": "..."}` |
| Valid + past_due (payment failed but not expired) | 200 | `{"valid": true, "status": "past_due", "expires_at": "...", ...}` |
| Valid + cancelled (still within paid period) | 200 | `{"valid": true, "status": "cancelled", "expires_at": "...", ...}` |
| Expired | 403 | `{"valid": false, "error": "License expired", "expired_at": "..."}` |
| Revoked | 403 | `{"valid": false, "error": "License revoked"}` |
| Invalid key | 403 | `{"valid": false, "error": "Invalid license key"}` |

**Design decision: return metadata, not just 200/403.** The `setup.sh` script can display the customer email and expiry date to confirm the right license is being used. The `status` field lets scripts show a warning if the license is `cancelled` or `past_due` (still works, but heads-up).

### Rate Limiting

```python
from slowapi import Limiter

# In main.py, the limiter is already configured
# In the router:

@router.post("/license/validate")
@limiter.limit("10/minute")  # Per IP — prevents brute force
async def validate_license(request: Request):
    ...
```

**Why 10/minute is enough:** `setup.sh` calls once. `sync-upstream.yml` calls once per week. Even aggressive debugging wouldn't hit 10/min. But a brute-force attempt would be throttled.

### Caching Strategy

**No server-side cache needed.** DynamoDB GetItem is single-digit milliseconds and costs $0.25 per million reads. At the expected volume (a few hundred license holders, each validating once per week), this is effectively free and not worth the complexity of a cache.

**Client-side:** `setup.sh` should cache the validation result locally (e.g., write a `.license_valid_until` file with the expiry date). On subsequent runs, check the local file first. If not expired, skip the HTTP call. This is a nice-to-have, not a requirement.

---

## 5. Usage in setup.sh and sync-upstream.yml

### setup.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

LICENSE_KEY="${COJOURNALIST_LICENSE_KEY:-}"

if [ -z "$LICENSE_KEY" ]; then
    echo "Error: COJOURNALIST_LICENSE_KEY environment variable not set."
    echo "Get your license key at https://www.cojournalist.ai/license"
    exit 1
fi

# Validate license
echo "Validating license..."
RESPONSE=$(curl -s -X POST -w "\n%{http_code}" \
    -H "Content-Type: application/json" \
    -d "{\"key\": \"${LICENSE_KEY}\"}" \
    "https://www.cojournalist.ai/api/license/validate" \
    --max-time 10 2>/dev/null || echo -e "\n000")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    EXPIRES=$(echo "$BODY" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4)
    STATUS=$(echo "$BODY" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "License valid (expires: ${EXPIRES}, status: ${STATUS})"

    if [ "$STATUS" = "cancelled" ]; then
        echo "Warning: Your subscription is cancelled. License works until ${EXPIRES}."
    fi
elif [ "$HTTP_CODE" = "403" ]; then
    ERROR=$(echo "$BODY" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
    echo "License validation failed: ${ERROR}"
    exit 1
elif [ "$HTTP_CODE" = "000" ]; then
    # Network error or endpoint down — grace period
    echo "Warning: Could not reach license server. Proceeding with grace period."
    echo "If this persists, check https://www.cojournalist.ai/status"
    # Continue execution — don't block users because of a transient outage
else
    echo "Unexpected response (HTTP ${HTTP_CODE}). Proceeding anyway."
fi

# ... rest of setup.sh
```

### sync-upstream.yml (GitHub Action)

```yaml
name: Sync Upstream

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday at 6 AM UTC
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Validate License
        id: license
        env:
          COJOURNALIST_LICENSE_KEY: ${{ secrets.COJOURNALIST_LICENSE_KEY }}
        run: |
          if [ -z "$COJOURNALIST_LICENSE_KEY" ]; then
            echo "::error::COJOURNALIST_LICENSE_KEY secret not set"
            exit 1
          fi

          HTTP_CODE=$(curl -s -X POST -o /tmp/license_response.json -w "%{http_code}" \
            -H "Content-Type: application/json" \
            -d "{\"key\": \"${COJOURNALIST_LICENSE_KEY}\"}" \
            "https://www.cojournalist.ai/api/license/validate" \
            --max-time 10 2>/dev/null || echo "000")

          if [ "$HTTP_CODE" = "200" ]; then
            echo "License valid"
            echo "valid=true" >> $GITHUB_OUTPUT
          elif [ "$HTTP_CODE" = "403" ]; then
            echo "::error::License invalid or expired"
            cat /tmp/license_response.json
            exit 1
          else
            # Endpoint unreachable — allow grace period
            echo "::warning::License server unreachable (HTTP $HTTP_CODE). Proceeding."
            echo "valid=grace" >> $GITHUB_OUTPUT
          fi

      - name: Checkout
        uses: actions/checkout@v4
        # ... rest of sync steps
```

### Grace Period When Endpoint is Down

**Policy: fail open on network errors, fail closed on explicit rejections.**

| Scenario | Behavior | Rationale |
|----------|----------|-----------|
| 200 (valid) | Proceed | Normal |
| 403 (invalid/expired) | **Exit 1** | Explicit rejection — honor it |
| Network timeout / 5xx / DNS failure | **Proceed with warning** | Don't punish paying customers for our outage |
| Repeated failures (>4 weeks) | Still proceed | The license has a known `expires_at`; client can cache it |

The scripts should never block a paying customer because of a transient server issue. The license key itself has an `expires_at` baked in — the validation endpoint is a convenience check, not a hard DRM gate.

---

## 6. DynamoDB vs Supabase Decision

**Recommendation: use DynamoDB (existing `scraping-jobs` table).**

| Factor | DynamoDB | Supabase (separate project) |
|--------|----------|---------------------------|
| Already deployed | Yes | No — new project, new credentials, new bill |
| Fits single-table pattern | Perfectly — LICENSE# and STRIPE_SUB# are just new PK prefixes | N/A |
| Latency | Single-digit ms (same region) | ~50ms (separate service, likely different region) |
| Cost at scale | Effectively free (<1000 reads/month) | Free tier covers it, but still another thing to manage |
| Operational overhead | Zero — same table, same IAM, same boto3 client | New connection string, new auth, new SDK |
| Backup/monitoring | Already configured | Needs new setup |

Supabase would only make sense if you wanted a separate admin dashboard with Supabase's built-in table editor for support staff. But for <1000 licenses, the DynamoDB records can be queried via the AWS console or a simple admin endpoint.

---

## 7. Config Changes

Add to `backend/app/config.py`:

```python
# Stripe (license key management)
stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
stripe_annual_price_id: str = os.getenv("STRIPE_ANNUAL_PRICE_ID", "")
```

Add to Render environment:
- `STRIPE_SECRET_KEY` — Stripe secret key
- `STRIPE_WEBHOOK_SECRET` — webhook signing secret (from Stripe dashboard)
- `STRIPE_ANNUAL_PRICE_ID` — the Price ID for the annual license product

Add `stripe` to `requirements.txt`:
```
stripe>=8.0.0
```

---

## 8. Router Registration

In `main.py`:

```python
from app.routers import license

# License key management — hidden from public API docs
app.include_router(license.router, prefix="/api", tags=["License"], include_in_schema=False)
```

The `POST /api/license/validate` endpoint is public (no auth required — the key is the auth, sent in the request body). The `/api/license/webhook` endpoint is secured by Stripe signature verification.

---

## 9. Stripe Setup Checklist

1. Create a Product in Stripe: "coJournalist Annual License"
2. Create a Price: annual recurring, set the amount
3. Create a Checkout link or embed Checkout on the site
4. Register webhook endpoint: `https://www.cojournalist.ai/api/license/webhook`
5. Select events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`, `invoice.payment_failed`
6. Copy the webhook signing secret to Render env vars
7. Add `STRIPE_SECRET_KEY` to Render env vars

---

## 10. File Summary

| File | Purpose |
|------|---------|
| `backend/app/routers/license.py` | Validation endpoint + Stripe webhook handler |
| `backend/app/services/license_key_service.py` | DynamoDB CRUD for LICENSE# and STRIPE_SUB# records |
| `backend/app/config.py` | New Stripe env vars |
| `backend/app/main.py` | Router registration |
| `docs/architecture/records-and-deduplication.md` | Add LICENSE# and STRIPE_SUB# record types |

No new tables. No new infrastructure. No new services to deploy. The entire feature is ~200 lines of Python added to the existing FastAPI backend.
