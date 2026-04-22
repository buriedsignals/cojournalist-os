"""
MuckRock compatibility proxy — keeps the pre-cutover cojournalist.ai URLs
alive while the real handlers live in Supabase Edge Functions.

Why this exists: MuckRock has two URLs registered against our OAuth client
(client_id 879742):

    - webhook:          https://www.cojournalist.ai/api/auth/webhook
    - OAuth callback:   https://cojournalist.ai/api/auth/callback   (apex — NOT www)

The apex vs www mismatch on the callback is deliberate: MuckRock's OAuth
registration predates the www-only app origin and requires the bare domain.
RFC 6749 §3.1.2.3 requires byte-exact match, so the `auth-muckrock` EF sends
`${MUCKROCK_CALLBACK_URL}` (= apex string) on both the authorize and token
exchange calls. Cloudflare/Render serves both apex and www, so this proxy
is reached regardless of which subdomain MuckRock calls back on.

Both URLs used to point at the FastAPI auth router. Post-cutover the handlers
moved to `billing-webhook` and `auth-muckrock` Edge Functions. Rather than
ask MuckRock to update their registration (paperwork, coordination, risk
of drift during the window), we proxy:

    POST /api/auth/webhook   → forward body + headers to the EF
    GET  /api/auth/callback  → 302 the browser to the EF callback

HMAC (body-signed) and OAuth state (signed blob in `state` query param)
both survive the proxy verbatim. Env overrides for self-hosted deploys:
`SUPABASE_BILLING_WEBHOOK_URL`, `SUPABASE_AUTH_CALLBACK_URL`.

DEPENDS ON: httpx (async HTTP client)
USED BY: main.py (mounted at /api/auth)
"""
import logging
import os
import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter()

SUPABASE_BILLING_WEBHOOK_URL = os.getenv(
    "SUPABASE_BILLING_WEBHOOK_URL",
    "https://gfmdziplticfoakhrfpt.supabase.co/functions/v1/billing-webhook",
)

SUPABASE_AUTH_CALLBACK_URL = os.getenv(
    "SUPABASE_AUTH_CALLBACK_URL",
    "https://gfmdziplticfoakhrfpt.supabase.co/functions/v1/auth-muckrock/callback",
)

# Startup-time allowlist so a misconfigured env can't turn the proxy into an
# open relay. Widen or relax for OSS self-hosters as needed.
_ALLOWED_HOSTS = ("supabase.co", "supabase.in")


def _validate_upstream(url: str, label: str) -> None:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise RuntimeError(f"{label} must be https with a hostname; got {url!r}")
    if not any(p.hostname == h or p.hostname.endswith("." + h) for h in _ALLOWED_HOSTS):
        raise RuntimeError(
            f"{label} must point at supabase.co/.in; got {url!r}. Update env or "
            "widen `_ALLOWED_HOSTS` for self-hosted deploys."
        )


_validate_upstream(SUPABASE_BILLING_WEBHOOK_URL, "SUPABASE_BILLING_WEBHOOK_URL")
_validate_upstream(SUPABASE_AUTH_CALLBACK_URL, "SUPABASE_AUTH_CALLBACK_URL")


# Strip hop-by-hop headers (RFC 7230 §6.1) + a few extras we never want to
# relay. Authorization is stripped because MuckRock's signature lives in the
# body, not headers — forwarding a bearer could confuse Kong.
_STRIP_HEADERS = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "authorization",
}


@router.post("/webhook")
async def forward_webhook(request: Request) -> Response:
    """Forward MuckRock webhook POSTs to the billing-webhook Edge Function."""
    body = await request.body()
    upstream_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _STRIP_HEADERS
    }
    start = time.monotonic()
    upstream = None
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=12.0, write=5.0, pool=2.0),
        ) as client:
            upstream = await client.post(
                SUPABASE_BILLING_WEBHOOK_URL,
                content=body,
                headers=upstream_headers,
            )
    except httpx.HTTPError:
        logger.exception("billing_webhook_proxy: upstream unreachable")
        # Sterile detail so DNS / cert errors don't leak upstream infra shape.
        raise HTTPException(status_code=502, detail="Upstream unavailable")
    finally:
        dur_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "billing_webhook_proxy status=%s upstream_ms=%d body_bytes=%d",
            upstream.status_code if upstream is not None else "error",
            dur_ms,
            len(body),
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            "content-type": upstream.headers.get(
                "content-type", "application/octet-stream",
            ),
        },
    )


@router.get("/callback")
async def forward_oauth_callback(request: Request) -> RedirectResponse:
    """Proxy MuckRock OAuth callback GETs to the auth-muckrock EF.

    Pure 302 — the browser does the second hop itself. Query params
    (`code`, `state`, optional `error`) are preserved end-to-end, so the
    signed `state` survives and the EF validates it exactly as if MuckRock
    had pointed at the EF directly.
    """
    query = request.url.query
    target = SUPABASE_AUTH_CALLBACK_URL + (f"?{query}" if query else "")
    logger.info(
        "auth_callback_proxy query_len=%d has_error=%s",
        len(query),
        "error=" in query,
    )
    resp = RedirectResponse(url=target, status_code=302)
    resp.headers["cache-control"] = "no-store"
    return resp
