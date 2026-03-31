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
import functools
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response
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


def _validate_license_key(key: str) -> tuple[dict | None, JSONResponse | None]:
    """Validate a license key. Returns (record, None) on success or (None, error_response) on failure."""
    service = LicenseKeyService()
    record = service.validate_key(key)

    if not record:
        return None, JSONResponse(
            status_code=403,
            content={"valid": False, "error": "Invalid license key"},
        )

    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        return None, JSONResponse(
            status_code=403,
            content={"valid": False, "error": "License expired", "expired_at": record["expires_at"]},
        )

    status = record.get("status", "active")
    if status == "revoked":
        return None, JSONResponse(
            status_code=403,
            content={"valid": False, "error": "License revoked"},
        )

    return record, None


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
    record, error = _validate_license_key(key)
    if error:
        return error

    status = record.get("status", "active")
    return {
        "valid": True,
        "status": status,
        "expires_at": record["expires_at"],
        "customer_email": record.get("customer_email"),
    }


def _resolve_gated_file(name: str) -> str:
    """Resolve a gated file path, checking Docker then local dev locations."""
    # Docker path: /workspace/backend/app/<name>
    docker_path = Path(__file__).resolve().parent.parent / name
    if docker_path.exists():
        return docker_path.read_text()

    # Local dev: map filenames to their repo-root locations
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    local_paths = {
        "SETUP_AGENT.md": repo_root / "automation" / "SETUP_AGENT.md",
        "setup.sh": repo_root / "automation" / "setup.sh",
        "sync-upstream.yml": repo_root / "automation" / "sync-upstream.yml",
        "render.yaml": repo_root / "deploy" / "render" / "render.yaml",
        "SETUP.md": repo_root / "deploy" / "SETUP.md",
    }
    local_path = local_paths.get(name)
    if local_path and local_path.exists():
        return local_path.read_text()

    return ""


@functools.lru_cache(maxsize=1)
def _load_gated_files() -> dict[str, str]:
    """Load all license-gated files (cached for process lifetime)."""
    names = ["SETUP_AGENT.md", "render.yaml", "setup.sh", "sync-upstream.yml", "SETUP.md"]
    return {name: _resolve_gated_file(name) for name in names}


@router.post("/license/setup-guide")
@limiter.limit("5/minute")
async def download_setup_guide(request: Request):
    """Download license-gated deployment files after license key validation.

    Accepts JSON body: {"key": "cjl_..."}

    Query params:
        ?file=setup-skill.md  — return single file as raw text
        (no param)            — return all files as JSON bundle

    Rate limited to 5/minute per IP.
    """
    body = await request.json()
    key = body.get("key", "")
    record, error = _validate_license_key(key)
    if error:
        return error

    # Single file mode: return raw content (no jq needed)
    requested_file = request.query_params.get("file")
    if requested_file:
        files = _load_gated_files()
        if requested_file not in files or not files[requested_file]:
            return JSONResponse(
                status_code=404,
                content={"error": f"File not found: {requested_file}"},
            )
        return Response(content=files[requested_file], media_type="text/plain")

    # Bundle mode: return all files as JSON (for frontend download button)
    files = _load_gated_files()
    if not any(files.values()):
        return JSONResponse(
            status_code=503,
            content={"error": "Setup files not available"},
        )

    return {"files": files}


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
    handled = {
        "checkout.session.completed",
        "invoice.paid",
        "customer.subscription.deleted",
        "invoice.payment_failed",
    }

    if event_type not in handled:
        return {"status": "ok"}

    # Convert StripeObject to plain dict — .get() doesn't work on StripeObjects
    data = json.loads(str(event["data"]["object"]))

    if event_type == "checkout.session.completed":
        await _handle_new_purchase(data)
    elif event_type == "invoice.paid":
        if data.get("billing_reason") == "subscription_cycle":
            await _handle_renewal(data)
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
    """Send the license key to the customer via Resend SDK."""
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set, skipping license email")
        return

    import resend

    resend.api_key = settings.resend_api_key

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f4;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f4;">
        <!-- Header -->
        <div style="padding: 32px 24px; text-align: center; border-bottom: 1px solid rgba(0, 0, 0, 0.06);">
            <img src="https://www.cojournalist.ai/static/logo-cojournalist.png" alt="coJournalist" style="height: 32px; width: 126px; margin-bottom: 16px;">
            <h1 style="color: #1a1917; margin: 0; font-size: 22px; font-weight: 600;">Your License Key</h1>
            <p style="color: #57534e; margin: 8px 0 0 0; font-size: 14px;">Self-Hosted Newsroom Edition</p>
        </div>

        <!-- Body -->
        <div style="padding: 32px 24px;">
            <p style="margin: 0 0 20px 0; font-size: 15px; color: #555;">Thank you for your purchase. Here is your license key:</p>

            <!-- License key box -->
            <div style="background: #ffffff; border-left: 4px solid #968bdf; border-radius: 8px; padding: 20px; margin: 0 0 24px 0;">
                <p style="margin: 0 0 8px 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #7c6fc7; font-weight: 600;">LICENSE KEY</p>
                <code style="font-family: 'SF Mono', 'Fira Code', Consolas, monospace; font-size: 15px; color: #1a1a1a; word-break: break-all; line-height: 1.8;">{license_key}</code>
            </div>

            <p style="margin: 0 0 32px 0; font-size: 13px; color: #888;">Save this key somewhere safe. It will not be shown again.</p>

            <!-- Getting started -->
            <div style="border-top: 1px solid rgba(0, 0, 0, 0.06); padding-top: 28px; text-align: center;">
                <h2 style="margin: 0 0 16px 0; font-size: 16px; color: #1a1a1a;">Get Started</h2>

                <a href="https://www.cojournalist.ai/setup"
                   style="display: inline-block; width: 100%; max-width: 360px; padding: 16px 32px; background-color: #7c6fc7; background: linear-gradient(135deg, #968bdf, #7c6fc7); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-sizing: border-box;">
                    Open Setup Guide
                </a>
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #78716c;">Use your license key to unlock the guide</p>
            </div>
        </div>

        <!-- Footer -->
        <div style="padding: 24px; text-align: center; border-top: 1px solid rgba(0, 0, 0, 0.06);">
            <p style="margin: 0; font-size: 12px; color: #a8a29e;">Buried Signals &mdash; coJournalist</p>
        </div>
    </div>
</body>
</html>
    """

    try:
        resend.Emails.send({
            "from": "coJournalist <noreply@cojournalist.ai>",
            "to": [email],
            "subject": "Your coJournalist License Key",
            "html": html_body,
        })
        logger.info(f"License key emailed to {email}")
    except Exception as e:
        logger.error(f"Failed to send license email: {e}")
