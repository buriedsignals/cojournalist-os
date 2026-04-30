"""Tests for the local FastAPI MuckRock broker."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import local_auth


def _settings():
    return SimpleNamespace(
        muckrock_client_id="mr-client",
        muckrock_client_secret="mr-secret",
        muckrock_base_url="https://accounts.muckrock.com",
        session_secret="test-session-secret",
        oauth_redirect_base="http://localhost:5173",
        email_allowlist="",
        supabase_url="https://proj.supabase.co",
        supabase_service_key="service-role-key",
        app_post_login_redirect="https://www.cojournalist.ai/auth/callback",
    )


def _mount() -> TestClient:
    app = FastAPI()
    app.include_router(local_auth.router, prefix="/api/auth")
    return TestClient(app, follow_redirects=False)


class _FakeMuckRock:
    def __init__(self):
        self.redirect_uri = None
        self.state = None
        self.exchange_calls = []

    def get_authorize_url(self, redirect_uri: str, state: str) -> str:
        self.redirect_uri = redirect_uri
        self.state = state
        return f"https://accounts.muckrock.com/openid/authorize?state={state}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        self.exchange_calls.append((code, redirect_uri))
        return {"access_token": "mr-access-token"}

    async def get_userinfo(self, access_token: str) -> dict:
        assert access_token == "mr-access-token"
        return {
            "uuid": "4f91a23a-6f13-4c6a-99b2-8f9ce5e7d2b1",
            "email": "reporter@example.com",
            "preferred_username": "reporter",
        }


class _FakeSupabaseAdmin:
    def __init__(self):
        self.created_users = []
        self.generate_link_calls = []

    async def create_user(self, attrs):
        self.created_users.append(attrs)

    async def generate_link(self, params):
        self.generate_link_calls.append(params)
        return SimpleNamespace(
            properties=SimpleNamespace(
                action_link="https://newsroom-project.supabase.co/auth/v1/verify?token=abc&type=magiclink",
            ),
        )


class _FakeSupabase:
    def __init__(self):
        self.auth = SimpleNamespace(admin=_FakeSupabaseAdmin())


def test_login_302s_to_muckrock_and_signs_local_redirect(monkeypatch):
    fake_muckrock = _FakeMuckRock()
    monkeypatch.setattr(local_auth, "get_settings", _settings)
    monkeypatch.setattr(local_auth, "_get_muckrock", lambda: fake_muckrock)

    client = _mount()
    res = client.get(
        "/api/auth/login?post_login_redirect=http://localhost:5173/auth/callback",
    )

    assert res.status_code == 302
    assert res.headers["location"].startswith("https://accounts.muckrock.com/openid/authorize")
    assert fake_muckrock.redirect_uri == "http://localhost:5173/api/auth/callback"

    payload = local_auth._verify_state(fake_muckrock.state)
    assert payload is not None
    assert payload["post_login_redirect"] == "http://localhost:5173/auth/callback"


def test_login_rejects_non_local_post_login_redirect(monkeypatch):
    monkeypatch.setattr(local_auth, "get_settings", _settings)
    monkeypatch.setattr(local_auth, "_get_muckrock", lambda: _FakeMuckRock())

    client = _mount()
    res = client.get(
        "/api/auth/login?post_login_redirect=https://cojournalist.ai/auth/callback",
    )

    assert res.status_code == 400
    assert res.json() == {"error": "invalid post_login_redirect"}


def test_callback_rewrites_magiclink_back_to_localhost(monkeypatch):
    fake_muckrock = _FakeMuckRock()
    fake_supabase = _FakeSupabase()

    async def _get_supabase():
        return fake_supabase

    async def _resolve(_action_link: str):
        return "https://www.cojournalist.ai/auth/callback?type=magiclink#access_token=aaa&refresh_token=bbb"

    monkeypatch.setattr(local_auth, "get_settings", _settings)
    monkeypatch.setattr(local_auth, "_get_muckrock", lambda: fake_muckrock)
    monkeypatch.setattr(local_auth, "_get_supabase_admin", _get_supabase)
    monkeypatch.setattr(local_auth, "_resolve_action_link_redirect", _resolve)

    state = local_auth._create_state("http://localhost:5173/auth/callback")
    client = _mount()
    res = client.get(f"/api/auth/callback?code=oauth-code&state={state}")

    assert res.status_code == 302
    assert (
        res.headers["location"]
        == "http://localhost:5173/auth/callback?type=magiclink#access_token=aaa&refresh_token=bbb"
    )
    assert fake_muckrock.exchange_calls == [("oauth-code", "http://localhost:5173/api/auth/callback")]

    admin_calls = fake_supabase.auth.admin
    assert admin_calls.created_users[0]["email"] == "reporter@example.com"
    assert admin_calls.generate_link_calls[0]["options"]["redirect_to"] == "https://www.cojournalist.ai/auth/callback"
