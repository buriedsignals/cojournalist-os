"""
Tests for the public same-origin broker to Supabase Edge Functions / MCP.

This covers the public contract advertised on cojournalist.ai:

  - /functions/v1/* forwards to the Supabase Edge Function gateway
  - /mcp* forwards to the mcp-server Edge Function
  - Authorization is preserved
  - apikey is injected from config when the caller does not send one
  - hop-by-hop headers are stripped
"""

from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import public_edge_proxy


def _mount() -> TestClient:
    app = FastAPI()
    app.include_router(public_edge_proxy.router)
    return TestClient(app)


class _FakeResp:
    def __init__(self, status_code: int, body: bytes, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.content = body
        self.headers = headers or {"content-type": "application/json"}


class _FakeClient:
    def __init__(self, response: _FakeResp):
        self._response = response
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def request(self, method: str, url: str, content: bytes | None, headers: dict):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "content": content,
                "headers": headers,
            },
        )
        return self._response


def test_functions_proxy_forwards_path_query_and_auth(monkeypatch):
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_anon_key", "anon-from-settings")
    fake = _FakeClient(_FakeResp(200, b'{"ok":true}'))

    with patch("app.routers.public_edge_proxy.httpx.AsyncClient", return_value=fake):
        client = _mount()
        res = client.get(
            "/functions/v1/openapi-spec?format=json",
            headers={
                "authorization": "Bearer cj_demo",
                "host": "www.cojournalist.ai",
            },
        )

    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://proj.supabase.co/functions/v1/openapi-spec?format=json"
    assert call["headers"]["authorization"] == "Bearer cj_demo"
    assert call["headers"]["apikey"] == "anon-from-settings"
    forwarded = {k.lower(): v for k, v in call["headers"].items()}
    assert "host" not in forwarded
    assert "content-length" not in forwarded


def test_functions_proxy_preserves_caller_apikey(monkeypatch):
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_anon_key", "anon-from-settings")
    fake = _FakeClient(_FakeResp(200, b"ok", {"content-type": "text/plain"}))

    with patch("app.routers.public_edge_proxy.httpx.AsyncClient", return_value=fake):
        client = _mount()
        res = client.get(
            "/functions/v1/scouts",
            headers={"apikey": "caller-apikey"},
        )

    assert res.status_code == 200
    assert res.text == "ok"
    assert fake.calls[0]["headers"]["apikey"] == "caller-apikey"


def test_mcp_proxy_maps_to_mcp_server_path(monkeypatch):
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_anon_key", "anon-from-settings")
    fake = _FakeClient(
        _FakeResp(
            200,
            b'{"issuer":"https://cojournalist.ai/mcp"}',
            {"content-type": "application/json", "cache-control": "max-age=300"},
        ),
    )

    with patch("app.routers.public_edge_proxy.httpx.AsyncClient", return_value=fake):
        client = _mount()
        res = client.get("/mcp/.well-known/oauth-authorization-server")

    assert res.status_code == 200
    assert res.json()["issuer"] == "https://cojournalist.ai/mcp"
    assert fake.calls[0]["url"] == (
        "https://proj.supabase.co/functions/v1/mcp-server/.well-known/oauth-authorization-server"
    )
    assert res.headers["cache-control"] == "max-age=300"


def test_proxy_returns_sterile_502_on_upstream_error(monkeypatch):
    monkeypatch.setattr(public_edge_proxy.settings, "supabase_url", "https://proj.supabase.co")

    class _BrokenClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("secret-infra-detail")

    with patch("app.routers.public_edge_proxy.httpx.AsyncClient", return_value=_BrokenClient()):
        client = _mount()
        res = client.get("/functions/v1/openapi-spec")

    assert res.status_code == 502
    assert res.json() == {"detail": "Upstream unavailable"}


def test_validate_supabase_base_rejects_non_supabase_host():
    with pytest.raises(RuntimeError, match="supabase"):
        public_edge_proxy._validate_supabase_base("https://evil.example/functions/v1")


def test_validate_supabase_base_accepts_localhost_http():
    public_edge_proxy._validate_supabase_base("http://127.0.0.1:54321")
