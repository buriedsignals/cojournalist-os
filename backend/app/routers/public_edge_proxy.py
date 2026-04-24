"""
Public broker proxy for Supabase Edge Functions and MCP.

Why this exists:
The hosted product advertises same-origin agent endpoints on cojournalist.ai:

  - /functions/v1/*  -> public REST / OpenAPI surface
  - /mcp*            -> remote MCP + OAuth discovery surface

The real handlers live in Supabase Edge Functions. This proxy keeps the public
contract stable, injects the public anon key server-side when needed, and
avoids sending users to raw project URLs for normal hosted usage.

Security model:
  - Upstream host is fixed from SUPABASE_URL and validated at startup/lazy use.
  - Authorization is forwarded verbatim.
  - apikey is forwarded when provided, otherwise populated from
    SUPABASE_ANON_KEY for hosted same-origin calls.
  - Hop-by-hop headers are stripped.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_SUPABASE_HOSTS = ("supabase.co", "supabase.in")
_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=15.0, pool=5.0)

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
}

_RELAY_RESPONSE_HEADERS = {
    "content-type",
    "cache-control",
    "location",
    "www-authenticate",
    "content-disposition",
}


def _validate_supabase_base(url: str) -> None:
    parsed = urlparse(url)
    if not parsed.hostname:
        raise RuntimeError(f"SUPABASE_URL must include a hostname; got {url!r}")
    if parsed.hostname in _LOCAL_HOSTS:
        if parsed.scheme != "http":
            raise RuntimeError(
                "Local SUPABASE_URL must be http://localhost or "
                f"http://127.0.0.1; got {url!r}",
            )
        return
    if parsed.scheme != "https":
        raise RuntimeError(f"SUPABASE_URL must use https; got {url!r}")
    if not any(
        parsed.hostname == host or parsed.hostname.endswith("." + host)
        for host in _ALLOWED_SUPABASE_HOSTS
    ):
        raise RuntimeError(
            "SUPABASE_URL must point at supabase.co/.in for hosted mode; "
            f"got {url!r}",
        )


def _supabase_base() -> str:
    base = (settings.supabase_url or os.getenv("SUPABASE_URL") or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="Supabase broker unavailable")
    try:
        _validate_supabase_base(base)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return base


def _upstream_url(prefix: str, path: str, query: str) -> str:
    base = _supabase_base()
    prefix = prefix.strip("/")
    path = path.strip("/")
    url = f"{base}/{prefix}"
    if path:
        url = f"{url}/{path}"
    if query:
        url = f"{url}?{query}"
    return url


def _forward_headers(request: Request) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _STRIP_HEADERS
    }
    if "apikey" not in {key.lower() for key in headers} and settings.supabase_anon_key:
        headers["apikey"] = settings.supabase_anon_key
    return headers


def _response_headers(upstream: httpx.Response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in upstream.headers.items():
        lower = key.lower()
        if (
            lower in _RELAY_RESPONSE_HEADERS
            or lower.startswith("x-")
            or lower.startswith("mcp-")
        ):
            headers[key] = value
    return headers


async def _proxy(request: Request, upstream_url: str) -> Response:
    body = await request.body()
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=False,
        ) as client:
            upstream = await client.request(
                request.method,
                upstream_url,
                content=body or None,
                headers=_forward_headers(request),
            )
    except httpx.HTTPError:
        logger.exception("public_edge_proxy upstream unreachable: %s", upstream_url)
        raise HTTPException(status_code=502, detail="Upstream unavailable")

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_response_headers(upstream),
    )


@router.api_route(
    "/functions/v1/{path:path}",
    methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy_edge_functions(path: str, request: Request) -> Response:
    upstream_url = _upstream_url("functions/v1", path, request.url.query)
    return await _proxy(request, upstream_url)


@router.api_route(
    "/mcp",
    methods=["GET", "POST", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy_mcp_root(request: Request) -> Response:
    upstream_url = _upstream_url("functions/v1/mcp-server", "", request.url.query)
    return await _proxy(request, upstream_url)


@router.api_route(
    "/mcp/{path:path}",
    methods=["GET", "POST", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy_mcp_path(path: str, request: Request) -> Response:
    upstream_url = _upstream_url("functions/v1/mcp-server", path, request.url.query)
    return await _proxy(request, upstream_url)
