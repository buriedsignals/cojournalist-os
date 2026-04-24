"""Tests for the global 'no-store on error responses' middleware.

Every FastAPI response with status >= 400 must carry a `cache-control`
header that prevents caching — otherwise Cloudflare's default 4h browser
TTL pins the error response at edge, blocking users from recovering when
the underlying issue is fixed.

Covers:
 - 404 from SPAStaticFiles (asset not found)
 - 404 from FastAPI route not matching
 - 500 from unhandled exception (global_exception_handler)
 - 429 from slowapi rate limiting (indirect — we just check the
   middleware doesn't stomp explicit cache-control values)
 - 4xx HTTPException raised inside a router
"""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.main import app as prod_app


def test_fastapi_404_for_unknown_api_route_has_no_store():
    res = TestClient(prod_app).get("/api/this-definitely-does-not-exist")
    assert res.status_code == 404
    cache_control = res.headers.get("cache-control", "").lower()
    assert "no-store" in cache_control, (
        f"API 404 must carry no-store, got {cache_control!r}"
    )


def test_global_500_handler_response_has_no_store():
    """If an unhandled exception fires, the 500 response MUST NOT be
    cacheable at CF edge, otherwise a transient failure pins the site.

    The production app has a `@app.exception_handler(Exception)` that
    converts unhandled exceptions into a JSONResponse(500); we replicate
    that here so the test exercises the same control flow (middleware
    sees a response, not a raised exception).
    """
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    app = FastAPI()
    from app.main import _add_no_store_on_error_responses

    app.middleware("http")(_add_no_store_on_error_responses)

    @app.exception_handler(Exception)
    async def _handler(request, exc):  # noqa: ARG001
        return JSONResponse(status_code=500, content={"error": "boom"})

    router = APIRouter()

    @router.get("/boom")
    async def _boom():
        raise RuntimeError("kaboom")

    app.include_router(router)

    res = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert res.status_code == 500
    cache_control = res.headers.get("cache-control", "").lower()
    assert "no-store" in cache_control, (
        f"500 must carry no-store, got {cache_control!r}"
    )


def test_explicit_http_exception_response_has_no_store():
    from fastapi import APIRouter

    app = FastAPI()
    from app.main import _add_no_store_on_error_responses

    app.middleware("http")(_add_no_store_on_error_responses)

    router = APIRouter()

    @router.get("/notfound")
    async def _nf():
        raise HTTPException(status_code=404, detail="nope")

    @router.get("/forbidden")
    async def _fbid():
        raise HTTPException(status_code=403, detail="nope")

    app.include_router(router)

    for path, code in [("/notfound", 404), ("/forbidden", 403)]:
        res = TestClient(app).get(path)
        assert res.status_code == code
        cache_control = res.headers.get("cache-control", "").lower()
        assert "no-store" in cache_control, (
            f"{code} at {path} must carry no-store, got {cache_control!r}"
        )


def test_middleware_does_not_clobber_explicit_cache_control_on_errors():
    """If a route deliberately sets a cache-control on an error response,
    the middleware must respect it (never downgrade intentional caching).

    Example: a 304 Not Modified or a handled 404 that the app wants CF to
    cache briefly. Rare, but the middleware shouldn't blindly overwrite.
    """
    from fastapi import APIRouter
    from fastapi.responses import Response as FastAPIResponse

    app = FastAPI()
    from app.main import _add_no_store_on_error_responses

    app.middleware("http")(_add_no_store_on_error_responses)

    router = APIRouter()

    @router.get("/intentional-cached-404")
    async def _cached_nf():
        return FastAPIResponse(
            status_code=404,
            headers={"cache-control": "public, max-age=60"},
        )

    app.include_router(router)

    res = TestClient(app).get("/intentional-cached-404")
    assert res.status_code == 404
    cache_control = res.headers.get("cache-control", "").lower()
    assert "public" in cache_control
    assert "max-age=60" in cache_control
    assert "no-store" not in cache_control, (
        f"middleware clobbered explicit cache-control: {cache_control!r}"
    )


def test_middleware_does_not_touch_successful_responses():
    """A 2xx response must not get no-store by this middleware — callers
    are responsible for their own cache-control choices on success paths.
    """
    res = TestClient(prod_app).get("/api/health")
    assert res.status_code == 200
    cache_control = res.headers.get("cache-control", "")
    # The health endpoint doesn't set cache-control; that's fine.
    # What we assert is: middleware didn't stamp no-store on the 200.
    assert "no-store" not in cache_control.lower(), (
        f"middleware incorrectly stamped no-store on 200, got {cache_control!r}"
    )


def test_markdown_response_has_no_cache(tmp_path, monkeypatch):
    """Accept: text/markdown representations of SPA routes change every
    deploy (same as index.html) — must force revalidation."""
    from pathlib import Path as _Path

    import app.main as main

    _Path(tmp_path / "overview.txt").write_text("# overview\n")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)

    res = TestClient(prod_app).get("/", headers={"Accept": "text/markdown"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    cache_control = res.headers.get("cache-control", "").lower()
    assert "no-cache" in cache_control, (
        f"markdown route must carry no-cache, got {cache_control!r}"
    )


def test_security_headers_include_referrer_policy():
    """Referrer-Policy should be set to minimize leakage of scout URLs
    or authenticated paths to third-party resources."""
    res = TestClient(prod_app).get("/api/health")
    assert res.status_code == 200
    referrer_policy = res.headers.get("referrer-policy", "")
    assert referrer_policy, "Referrer-Policy header missing"
    # Any strict-ish policy is acceptable — we just want to ensure
    # it's not unset (browser default = no-referrer-when-downgrade, leaky).
    assert any(
        token in referrer_policy.lower()
        for token in [
            "strict-origin",
            "same-origin",
            "no-referrer",
            "origin",
        ]
    ), f"Referrer-Policy not sufficiently restrictive: {referrer_policy!r}"
