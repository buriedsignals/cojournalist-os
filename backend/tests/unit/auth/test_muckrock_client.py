"""
Unit tests for the MuckRock OAuth client.

These tests verify that:
1. Authorization URL is correctly built with all required params
2. End session URL points to the correct endpoint
3. Token exchange sends correct form data and handles errors
4. Userinfo fetches with Bearer token and handles errors
5. Token refresh sends correct form data and handles errors
6. Client credentials token retrieval and caching
7. User/org data endpoints use client_credentials access token
"""
import pytest
import time
import httpx
from unittest.mock import AsyncMock, patch

from app.services.muckrock_client import (
    MuckRockClient,
    MuckRockClientError,
    _token_cache,
)


@pytest.fixture
def client():
    """MuckRockClient with test credentials."""
    return MuckRockClient(
        client_id="test-client-id",
        client_secret="test-client-secret",
        base_url="https://accounts.muckrock.com",
    )


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Reset the module-level token cache before each test."""
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0.0
    yield
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0.0


def _mock_async_client(mock_instance):
    """Wire up async context manager on a mock httpx.AsyncClient instance."""
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=False)


class TestGetAuthorizeUrl:
    """Tests for building the OAuth authorization URL."""

    def test_contains_all_params(self, client):
        """URL should contain response_type, client_id, redirect_uri, state, scope."""
        url = client.get_authorize_url(
            redirect_uri="https://app.example.com/callback",
            state="random-state-123",
        )
        assert url.startswith("https://accounts.muckrock.com/openid/authorize?")
        assert "response_type=code" in url
        assert "client_id=test-client-id" in url
        assert "redirect_uri=https" in url
        assert "state=random-state-123" in url
        assert "scope=openid" in url

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash on base_url should not create double slash."""
        c = MuckRockClient("id", "secret", "https://accounts.muckrock.com/")
        url = c.get_authorize_url("https://app.example.com/cb", "s")
        assert "muckrock.com//openid" not in url
        assert "muckrock.com/openid/authorize" in url


class TestGetEndSessionUrl:
    """Tests for the end-session URL."""

    def test_returns_correct_url(self, client):
        """Should return the OIDC end-session endpoint."""
        assert client.get_end_session_url() == (
            "https://accounts.muckrock.com/openid/end-session"
        )


class TestExchangeCode:
    """Tests for token exchange."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Successful exchange should return parsed JSON tokens."""
        token_response = {
            "access_token": "at-123",
            "refresh_token": "rt-456",
            "id_token": "id-789",
            "token_type": "Bearer",
        }
        mock_response = httpx.Response(200, json=token_response)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.exchange_code("auth-code", "https://app/cb")

        assert result == token_response
        mock_instance.post.assert_called_once()
        call_kwargs = mock_instance.post.call_args
        assert "authorization_code" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_failure_raises(self, client):
        """Non-200 response should raise MuckRockClientError."""
        mock_response = httpx.Response(400, json={"error": "invalid_grant"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            with pytest.raises(MuckRockClientError, match="status 400"):
                await client.exchange_code("bad-code", "https://app/cb")


class TestGetUserinfo:
    """Tests for the userinfo endpoint."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Should return user info dict with Bearer auth."""
        user_data = {
            "sub": "user-uuid",
            "name": "Test User",
            "email": "test@example.com",
            "organizations": [{"uuid": "org-1", "name": "Org"}],
        }
        mock_response = httpx.Response(200, json=user_data)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.get_userinfo("at-123")

        assert result == user_data
        call_args = mock_instance.get.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer at-123"

    @pytest.mark.asyncio
    async def test_failure_raises(self, client):
        """Non-200 should raise MuckRockClientError."""
        mock_response = httpx.Response(401, json={"error": "unauthorized"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            with pytest.raises(MuckRockClientError, match="status 401"):
                await client.get_userinfo("bad-token")


class TestRefreshAccessToken:
    """Tests for token refresh."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Successful refresh should return new tokens."""
        new_tokens = {
            "access_token": "at-new",
            "refresh_token": "rt-new",
            "token_type": "Bearer",
        }
        mock_response = httpx.Response(200, json=new_tokens)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.refresh_access_token("rt-456")

        assert result == new_tokens

    @pytest.mark.asyncio
    async def test_failure_raises(self, client):
        """Non-200 should raise MuckRockClientError."""
        mock_response = httpx.Response(400, json={"error": "invalid_grant"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            with pytest.raises(MuckRockClientError, match="status 400"):
                await client.refresh_access_token("bad-rt")


class TestGetClientCredentialsToken:
    """Tests for OAuth2 client_credentials token retrieval and caching."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Should POST to /openid/token with Basic auth and grant_type."""
        token_response = {"access_token": "cc-token-123", "expires_in": 3600}
        mock_response = httpx.Response(200, json=token_response)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.get_client_credentials_token()

        assert result == "cc-token-123"
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "https://accounts.muckrock.com/openid/token"
        assert call_args[1]["data"]["grant_type"] == "client_credentials"
        assert call_args[1]["data"]["client_id"] == "test-client-id"
        assert call_args[1]["data"]["client_secret"] == "test-client-secret"

    @pytest.mark.asyncio
    async def test_caching(self, client):
        """Second call should return cached token without hitting /openid/token."""
        token_response = {"access_token": "cc-cached", "expires_in": 3600}
        mock_response = httpx.Response(200, json=token_response)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            first = await client.get_client_credentials_token()
            second = await client.get_client_credentials_token()

        assert first == "cc-cached"
        assert second == "cc-cached"
        # Only one POST — the second call used cache
        assert mock_instance.post.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expiry(self, client):
        """Expired cache should trigger a fresh token request."""
        token_response = {"access_token": "cc-fresh", "expires_in": 3600}
        mock_response = httpx.Response(200, json=token_response)

        # Pre-populate cache with an expired token
        _token_cache["token"] = "cc-stale"
        _token_cache["expires_at"] = time.time() - 1

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.get_client_credentials_token()

        assert result == "cc-fresh"
        mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_raises(self, client):
        """Non-200 from /openid/token should raise MuckRockClientError."""
        mock_response = httpx.Response(401, json={"error": "invalid_client"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            with pytest.raises(MuckRockClientError, match="status 401"):
                await client.get_client_credentials_token()


class TestFetchUserData:
    """Tests for user data fetching via client_credentials token."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Should fetch user data using a client_credentials access token."""
        user_data = {"uuid": "user-uuid", "name": "Test User"}
        token_response = httpx.Response(
            200, json={"access_token": "cc-token", "expires_in": 3600}
        )
        user_response = httpx.Response(200, json=user_data)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            # First call: POST /openid/token, second call: GET /api/users/{uuid}/
            mock_instance.post = AsyncMock(return_value=token_response)
            mock_instance.get = AsyncMock(return_value=user_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.fetch_user_data("user-uuid")

        assert result == user_data
        # Verify token endpoint was called with credentials in form body
        token_call = mock_instance.post.call_args
        assert token_call[1]["data"]["client_id"] == "test-client-id"
        assert token_call[1]["data"]["client_secret"] == "test-client-secret"
        # Verify user endpoint used the access token (not client_secret)
        user_call = mock_instance.get.call_args
        assert "/api/users/user-uuid/" in user_call[0][0]
        assert user_call[1]["headers"]["Authorization"] == "Bearer cc-token"

    @pytest.mark.asyncio
    async def test_failure_raises(self, client):
        """Non-200 should raise MuckRockClientError."""
        token_response = httpx.Response(
            200, json={"access_token": "cc-token", "expires_in": 3600}
        )
        user_response = httpx.Response(404, json={"detail": "not found"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=token_response)
            mock_instance.get = AsyncMock(return_value=user_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            with pytest.raises(MuckRockClientError, match="status 404"):
                await client.fetch_user_data("nonexistent")


class TestAuthenticatedHeadersFallback:
    """Tests for client_credentials → raw CLIENT_SECRET fallback."""

    @pytest.mark.asyncio
    async def test_fetch_user_data_falls_back_to_client_secret(self):
        """If client_credentials token fails, fall back to raw CLIENT_SECRET as Bearer."""
        mc = MuckRockClient("test-id", "test-secret", "https://accounts.muckrock.com")

        # Clear token cache so client_credentials is attempted
        from app.services.muckrock_client import _token_cache
        _token_cache["token"] = None
        _token_cache["expires_at"] = 0.0

        token_fail = httpx.Response(400, text="invalid_scope")
        user_success = httpx.Response(200, json={"uuid": "user-1", "email": "test@example.com"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=token_fail)  # client_credentials fails
            mock_client.get = AsyncMock(return_value=user_success)  # fallback Bearer succeeds
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await mc.fetch_user_data("user-1")
            assert result["uuid"] == "user-1"

            # Verify the GET used raw CLIENT_SECRET as Bearer (fallback)
            get_call = mock_client.get.call_args
            assert get_call.kwargs.get("headers", {}).get("Authorization") == "Bearer test-secret"


class TestFetchOrgData:
    """Tests for org data fetching via client_credentials token."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Should fetch org data using a client_credentials access token."""
        org_data = {"uuid": "org-uuid", "name": "Test Org"}
        token_response = httpx.Response(
            200, json={"access_token": "cc-token", "expires_in": 3600}
        )
        org_response = httpx.Response(200, json=org_data)

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=token_response)
            mock_instance.get = AsyncMock(return_value=org_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            result = await client.fetch_org_data("org-uuid")

        assert result == org_data
        # Verify org endpoint used the access token (not client_secret)
        org_call = mock_instance.get.call_args
        assert "/api/organizations/org-uuid/" in org_call[0][0]
        assert org_call[1]["headers"]["Authorization"] == "Bearer cc-token"

    @pytest.mark.asyncio
    async def test_failure_raises(self, client):
        """Non-200 should raise MuckRockClientError."""
        token_response = httpx.Response(
            200, json={"access_token": "cc-token", "expires_in": 3600}
        )
        org_response = httpx.Response(500, json={"detail": "server error"})

        with patch("app.services.muckrock_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=token_response)
            mock_instance.get = AsyncMock(return_value=org_response)
            _mock_async_client(mock_instance)
            MockClient.return_value = mock_instance

            with pytest.raises(MuckRockClientError, match="status 500"):
                await client.fetch_org_data("org-uuid")
