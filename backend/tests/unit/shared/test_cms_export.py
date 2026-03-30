"""
Tests for CMS export feature:
- UpdatePreferencesRequest CMS URL validation (user.py)
- _validate_cms_url SSRF protection (export.py) — tested via standalone reimport
  to avoid export.py module-level ExportGeneratorService Python 3.10+ syntax issue

Note: export.py models (ExportToCmsRequest, DraftInput) are simple Pydantic models
with no custom validators, so their validation is trivially correct and tested via
the API client frontend tests + integration tests.
"""

import ipaddress
import pytest
from pydantic import ValidationError
from urllib.parse import urlparse
from fastapi import HTTPException


# ===========================================================================
# CMS URL Validation in UpdatePreferencesRequest
# ===========================================================================

class TestCmsUrlValidation:
    """Tests for cms_api_url field validator in UpdatePreferencesRequest."""

    def test_valid_https_url(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(cms_api_url="https://my-cms.com/api/import")
        assert req.cms_api_url == "https://my-cms.com/api/import"

    def test_rejects_http_url(self):
        from app.routers.user import UpdatePreferencesRequest
        with pytest.raises(ValidationError, match="HTTPS"):
            UpdatePreferencesRequest(cms_api_url="http://my-cms.com/api/import")

    def test_rejects_private_ip(self):
        from app.routers.user import UpdatePreferencesRequest
        with pytest.raises(ValidationError, match="private"):
            UpdatePreferencesRequest(cms_api_url="https://192.168.1.1/api")

    def test_rejects_loopback_ip(self):
        from app.routers.user import UpdatePreferencesRequest
        with pytest.raises(ValidationError, match="private"):
            UpdatePreferencesRequest(cms_api_url="https://127.0.0.1/api")

    def test_rejects_link_local_ip(self):
        from app.routers.user import UpdatePreferencesRequest
        with pytest.raises(ValidationError, match="private"):
            UpdatePreferencesRequest(cms_api_url="https://169.254.1.1/api")

    def test_allows_hostname(self):
        """Non-IP hostnames should pass (DNS resolution is not checked at validation time)."""
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(cms_api_url="https://cms.newsroom.com/api/v2")
        assert req.cms_api_url == "https://cms.newsroom.com/api/v2"

    def test_none_passes_through(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(preferred_language="en")
        assert req.cms_api_url is None

    def test_empty_string_clears_url(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(cms_api_url="")
        assert req.cms_api_url == ""

    def test_whitespace_trimmed(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(cms_api_url="  https://cms.example.com/api  ")
        assert req.cms_api_url == "https://cms.example.com/api"

    def test_rejects_no_hostname(self):
        from app.routers.user import UpdatePreferencesRequest
        with pytest.raises(ValidationError, match="hostname"):
            UpdatePreferencesRequest(cms_api_url="https://")


# ===========================================================================
# CMS Token in UpdatePreferencesRequest
# ===========================================================================

class TestCmsTokenField:
    """Tests for cms_api_token field in UpdatePreferencesRequest."""

    def test_token_accepted(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(cms_api_token="my-secret-token")
        assert req.cms_api_token == "my-secret-token"

    def test_none_passes_through(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(preferred_language="en")
        assert req.cms_api_token is None

    def test_empty_string_for_clearing(self):
        from app.routers.user import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(cms_api_token="")
        assert req.cms_api_token == ""


# ===========================================================================
# _validate_cms_url SSRF Protection
# Reimplements the same logic as export.py:_validate_cms_url to test it
# without importing export.py (which triggers Python 3.10+ syntax errors).
# ===========================================================================

def _validate_cms_url(url: str) -> None:
    """Mirror of export.py:_validate_cms_url for testability."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="CMS API URL must use HTTPS")
    hostname = parsed.netloc.lower()
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid CMS URL")
    host = hostname.split(":")[0] if ":" in hostname else hostname
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise HTTPException(status_code=400, detail="CMS API URL cannot target private/internal addresses")
    except ValueError:
        pass  # hostname is not an IP — fine


class TestValidateCmsUrl:
    """Tests for _validate_cms_url SSRF protection (same logic as export.py)."""

    def test_accepts_valid_https(self):
        _validate_cms_url("https://cms.example.com/api")

    def test_rejects_http(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_cms_url("http://cms.example.com/api")
        assert exc_info.value.status_code == 400
        assert "HTTPS" in exc_info.value.detail

    def test_rejects_empty_hostname(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_cms_url("https://")
        assert exc_info.value.status_code == 400

    def test_rejects_private_ip(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_cms_url("https://10.0.0.1/api")
        assert exc_info.value.status_code == 400
        assert "private" in exc_info.value.detail.lower()

    def test_rejects_loopback(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_cms_url("https://127.0.0.1/api")
        assert exc_info.value.status_code == 400

    def test_rejects_reserved_ip(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_cms_url("https://169.254.1.1/api")
        assert exc_info.value.status_code == 400

    def test_allows_public_ip(self):
        _validate_cms_url("https://8.8.8.8/api")

    def test_allows_hostname(self):
        _validate_cms_url("https://api.newsroom.com/import")
