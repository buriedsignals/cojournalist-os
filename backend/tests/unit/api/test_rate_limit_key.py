"""Tests for `_client_ip_key` — slowapi key function that respects
Cloudflare's `CF-Connecting-IP` header when the request came through CF.

Regression guard: without this, all traffic behind Cloudflare buckets into
one rate-limit entry because `get_remote_address` returns the CF edge IP.
"""
from types import SimpleNamespace

import pytest

from app.main import _client_ip_key


def _req(headers: dict[str, str], client_host: str = "198.51.100.1"):
    """Minimal Starlette-ish request with the fields _client_ip_key touches.

    `get_remote_address` pulls from `request.client.host`, so we provide a
    `client` attribute with a `host` field alongside the headers map.
    """
    return SimpleNamespace(
        headers={k.lower(): v for k, v in headers.items()},
        client=SimpleNamespace(host=client_host),
    )


def test_returns_cf_connecting_ip_when_cf_ray_present():
    r = _req({"CF-Ray": "abc123-ZRH", "CF-Connecting-IP": "203.0.113.5"})
    assert _client_ip_key(r) == "203.0.113.5"


def test_falls_back_to_client_host_when_cf_ray_absent():
    # Non-Cloudflare request (e.g. local dev, curl direct to origin).
    r = _req({"CF-Connecting-IP": "203.0.113.5"}, client_host="198.51.100.42")
    # No CF-Ray — must NOT trust the header; use transport address.
    assert _client_ip_key(r) == "198.51.100.42"


def test_falls_back_when_cf_ray_present_but_no_cf_connecting_ip():
    # Malformed CF hop — CF-Ray but no CF-Connecting-IP: fall back safely.
    r = _req({"CF-Ray": "abc123"}, client_host="198.51.100.99")
    assert _client_ip_key(r) == "198.51.100.99"
