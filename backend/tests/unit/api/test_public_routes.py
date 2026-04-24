from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
import app.main as main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_public_skills_route_serves_prerendered_html(monkeypatch, tmp_path):
    _write(tmp_path / "index.html", "<html>root</html>")
    _write(tmp_path / "skills/index.html", "<html>skills</html>")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)

    res = TestClient(app).get("/skills")

    assert res.status_code == 200
    assert "skills" in res.text
    assert "root" not in res.text


def test_public_skill_markdown_file_is_served_directly(monkeypatch, tmp_path):
    _write(tmp_path / "skills/cojournalist.md", "# coJournalist skill\n")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)

    res = TestClient(app).get("/skills/cojournalist.md")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert "# coJournalist skill" in res.text


def test_public_legacy_skill_serves_root_skill_file(monkeypatch, tmp_path):
    _write(tmp_path / "skill.md", "# legacy skill\n")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)

    res = TestClient(app).get("/skill.md")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert "# legacy skill" in res.text


def test_swagger_route_serves_prerendered_html_and_allows_unpkg(monkeypatch, tmp_path):
    _write(tmp_path / "swagger/index.html", "<html>swagger</html>")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)

    res = TestClient(app).get("/swagger")

    assert res.status_code == 200
    assert "swagger" in res.text
    assert "https://unpkg.com" in res.headers["content-security-policy"]
