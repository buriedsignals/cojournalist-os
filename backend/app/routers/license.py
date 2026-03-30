"""
License key validation and Stripe webhook handler.

PURPOSE: Two endpoints for license key lifecycle:
- POST /license/validate — validates a license key (public, rate limited)
- POST /license/webhook — handles Stripe webhook events (signature verified)

DEPENDS ON: services/license_key_service.py, config (Stripe keys), stripe SDK
USED BY: automation/setup.sh, automation/sync-upstream.yml

No authentication required on /license/validate — the key IS the credential.
The /license/webhook endpoint is secured by Stripe signature verification.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.services.license_key_service import LicenseKeyService

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter for validation endpoint — prevents brute force
limiter = Limiter(key_func=get_remote_address)


def _generate_license_key() -> str:
    """Generate a license key.

    Format: cjl_XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
    - Prefix: cjl_ (coJournalist License)
    - 4 groups of 8 hex chars separated by hyphens
    - 128 bits of entropy (token_hex, no ambiguous chars)
    - Total length: 39 chars

    The key is shown to the user ONCE (at purchase) and emailed.
    Only the SHA-256 hash is stored.
    """
    parts = [secrets.token_hex(4) for _ in range(4)]  # 4 bytes = 8 hex chars each
    return "cjl_" + "-".join(parts)


@router.post("/license/validate")
@limiter.limit("10/minute")
async def validate_license(request: Request):
    """Validate a license key.

    Accepts JSON body: {"key": "cjl_..."}

    Returns:
        200 with metadata if valid and not expired.
        403 if invalid, expired, or revoked.

    No authentication required — the key IS the credential.
    Rate limited to 10/minute per IP to prevent brute force.
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


@router.post("/license/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for license key management.

    Events handled:
    - checkout.session.completed: Generate new license key
    - invoice.paid (renewal only): Extend expiry by 1 year
    - customer.subscription.deleted: Mark as cancelled
    - invoice.payment_failed: Mark as past_due

    Secured by Stripe signature verification.
    """
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
    # Convert StripeObject to plain dict — .get() doesn't work on StripeObjects
    import json
    data = json.loads(str(event["data"]["object"]))

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
    """Generate license key on first purchase.

    Idempotent: checks if a license already exists for the subscription
    before generating a new one (Stripe can redeliver webhooks).
    """
    subscription_id = session.get("subscription")

    # Idempotency: check if license already exists for this subscription
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

    # Store in DynamoDB
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
    """Extend license expiry on successful annual renewal.

    Extends from current expiry (not from now) to avoid drift.
    """
    subscription_id = invoice.get("subscription")
    service = LicenseKeyService()

    license_record = service.get_by_subscription(subscription_id)
    if not license_record:
        logger.warning(f"No license found for subscription {subscription_id}")
        return

    # Extend by 1 year from current expiry (not from now -- avoids drift)
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


async def _send_license_email(email: str, license_key: str):
    """Send the license key to the customer via Resend.

    Uses the same Resend HTTP API pattern as notification_service.py.
    """
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping license email")
        return

    import httpx

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto;">
        <!-- Header -->
        <div style="background: #f5f5f4; padding: 32px 24px; border-radius: 12px 12px 0 0; border: 1px solid #e7e5e4; border-bottom: none; text-align: center;">
            <img src="https://www.cojournalist.ai/logo-cojournalist.png" alt="coJournalist" style="height: 32px; margin-bottom: 16px;" />
            <h1 style="color: #1a1917; margin: 0; font-size: 22px; font-weight: 600;">Your License Key</h1>
            <p style="color: #57534e; margin: 8px 0 0 0; font-size: 14px;">Self-Hosted Newsroom Edition</p>
        </div>

        <!-- Body -->
        <div style="background: white; padding: 32px 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="margin: 0 0 20px 0; font-size: 15px; color: #555;">Thank you for your purchase. Here is your license key:</p>

            <!-- License key box -->
            <div style="background: #f8f9fa; border-left: 4px solid #4f46e5; border-radius: 8px; padding: 20px; margin: 0 0 24px 0;">
                <p style="margin: 0 0 8px 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #4f46e5; font-weight: 600;">LICENSE KEY</p>
                <code style="font-family: 'SF Mono', 'Fira Code', Consolas, monospace; font-size: 15px; color: #1a1a1a; word-break: break-all; line-height: 1.8;">{license_key}</code>
            </div>

            <p style="margin: 0 0 24px 0; font-size: 13px; color: #888;">Save this key somewhere safe. It will not be shown again.</p>

            <!-- Getting started -->
            <div style="border-top: 1px solid #e5e7eb; padding-top: 24px; margin-bottom: 24px;">
                <h2 style="margin: 0 0 16px 0; font-size: 16px; color: #1a1a1a;">Getting Started</h2>

                <div style="margin-bottom: 12px; padding: 12px 16px; background: #f8f9fa; border-radius: 6px;">
                    <p style="margin: 0; font-size: 14px;"><strong style="color: #4f46e5;">1.</strong> Clone the repo</p>
                    <code style="font-size: 12px; color: #666;">git clone https://github.com/buriedsignals/cojournalist-os</code>
                </div>

                <div style="margin-bottom: 12px; padding: 12px 16px; background: #f8f9fa; border-radius: 6px;">
                    <p style="margin: 0; font-size: 14px;"><strong style="color: #4f46e5;">2.</strong> Open in your AI coding agent (Claude Code, Codex, Cursor, etc.)</p>
                </div>

                <div style="margin-bottom: 12px; padding: 12px 16px; background: #f8f9fa; border-radius: 6px;">
                    <p style="margin: 0; font-size: 14px;"><strong style="color: #4f46e5;">3.</strong> Load the setup skill and follow the prompts</p>
                    <code style="font-size: 12px; color: #666;">Read automation/setup-skill.md and set up coJournalist</code>
                </div>
            </div>

            <!-- CTA button -->
            <div style="text-align: center; margin-bottom: 8px;">
                <a href="https://github.com/buriedsignals/cojournalist-os/blob/main/automation/setup-skill.md"
                   style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #4f46e5, #4338ca); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                    View Setup Guide
                </a>
            </div>
            <p style="text-align: center; margin: 8px 0 0 0; font-size: 12px; color: #999;">
                <a href="https://github.com/buriedsignals/cojournalist-os" style="color: #4f46e5; text-decoration: none;">github.com/buriedsignals/cojournalist-os</a>
            </p>
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding: 24px 0;">
            <p style="margin: 0; font-size: 12px; color: #999;">Buried Signals &mdash; coJournalist</p>
        </div>
    </div>
</body>
</html>
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "coJournalist <noreply@cojournalist.ai>",
                    "to": [email],
                    "subject": "Your coJournalist License Key",
                    "html": html_body,
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info(f"License key emailed to {email}")
            else:
                logger.error(f"Failed to email license key: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Failed to send license email: {e}")
