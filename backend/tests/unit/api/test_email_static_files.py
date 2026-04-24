"""Tests for EmailStaticFiles — the `/static/*` mount used by email images.

`/static/*` exists so email templates can reference absolute URLs like
`https://www.cojournalist.ai/static/logo-cojournalist.png` for Resend to
fetch at send time. Without restrictions, mounting `FRONTEND_DIST` there
would duplicate the entire SvelteKit build surface (`/static/_app/immutable/*`,
`/static/index.html`, `/static/overview.txt`, etc.) — harmless content-wise
but architecturally wrong and a larger footprint to reason about.

EmailStaticFiles enforces:
- root-level paths only (no `/` in the path segment)
- only image extensions (.png / .svg / .jpg / .jpeg / .gif / .webp / .ico)
- successful responses get `cache-control: public, max-age=86400`
- 404s carry `no-store`
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import EmailStaticFiles


def _build_static_root(root: Path) -> None:
    (root / "logo-cojournalist.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (root / "og-image.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (root / "overview.txt").write_text("not for /static")
    (root / "index.html").write_text("not for /static")
    (root / "_app" / "immutable" / "entry").mkdir(parents=True, exist_ok=True)
    (root / "_app" / "immutable" / "entry" / "start.HASH.js").write_text("js")


def _client(tmp_path: Path) -> TestClient:
    _build_static_root(tmp_path)
    app = FastAPI()
    app.mount("/static", EmailStaticFiles(directory=str(tmp_path)), name="static")
    return TestClient(app)


def test_root_level_image_served_with_long_cache(tmp_path):
    res = _client(tmp_path).get("/static/logo-cojournalist.png")
    assert res.status_code == 200
    cache_control = res.headers.get("cache-control", "").lower()
    assert "public" in cache_control, f"{cache_control!r}"
    assert "max-age=86400" in cache_control, f"{cache_control!r}"


def test_subdirectory_paths_are_404(tmp_path):
    """Prevents /static/ from being an alternate route into _app/immutable/
    or any other nested directory in the SvelteKit build tree.

    (`../` traversal cases are normalized by the HTTP client / Starlette
    routing layer before they reach EmailStaticFiles, so we don't test
    them here — they get a 404 by never matching the /static mount.)
    """
    client = _client(tmp_path)
    for blocked in [
        "/static/_app/immutable/entry/start.HASH.js",
        "/static/some/nested/file.png",
    ]:
        res = client.get(blocked)
        assert res.status_code == 404, f"{blocked} returned {res.status_code}"
        cache_control = res.headers.get("cache-control", "").lower()
        assert "no-store" in cache_control, (
            f"{blocked}: expected no-store, got cache-control={cache_control!r}"
        )


def test_non_image_extensions_are_404(tmp_path):
    """/static/ only serves image files — not HTML, text, markdown, JS, etc."""
    client = _client(tmp_path)
    for blocked in ["/static/overview.txt", "/static/index.html"]:
        res = client.get(blocked)
        assert res.status_code == 404, f"{blocked} returned {res.status_code}"
        assert "no-store" in res.headers.get("cache-control", "").lower()


def test_missing_image_returns_no_store_404(tmp_path):
    res = _client(tmp_path).get("/static/not-a-real-logo.png")
    assert res.status_code == 404
    assert "no-store" in res.headers.get("cache-control", "").lower()


def test_other_image_extensions_all_served(tmp_path):
    _build_static_root(tmp_path)
    # Add one file per allowed extension and verify each is reachable.
    for name, body in [
        ("icon.svg", b"<svg></svg>"),
        ("photo.jpg", b"\xff\xd8\xff\xe0fake"),
        ("photo.jpeg", b"\xff\xd8\xff\xe0fake"),
        ("anim.gif", b"GIF89a"),
        ("pic.webp", b"RIFF\x00\x00\x00\x00WEBP"),
        ("tab.ico", b"\x00\x00\x01\x00"),
    ]:
        (tmp_path / name).write_bytes(body)

    app = FastAPI()
    app.mount("/static", EmailStaticFiles(directory=str(tmp_path)), name="static")
    client = TestClient(app)

    for name in ["icon.svg", "photo.jpg", "photo.jpeg", "anim.gif", "pic.webp", "tab.ico"]:
        res = client.get(f"/static/{name}")
        assert res.status_code == 200, f"{name} returned {res.status_code}"
