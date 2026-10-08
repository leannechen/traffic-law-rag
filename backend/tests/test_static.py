from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.static import mount_frontend


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "a.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("secret")
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, str]:
        return {"ok": "yes"}

    mount_frontend(app, tmp_path)
    return TestClient(app)


def test_serves_index_at_root_and_for_spa_routes(client: TestClient) -> None:
    assert client.get("/").text == "<html>app</html>"
    assert client.get("/eval").text == "<html>app</html>"


def test_serves_real_files(client: TestClient) -> None:
    assert client.get("/assets/a.js").text == "console.log(1)"


def test_api_routes_still_win(client: TestClient) -> None:
    assert client.get("/api/ping").json() == {"ok": "yes"}


def test_unknown_api_path_is_404_not_html(client: TestClient) -> None:
    assert client.get("/api/nope").status_code == 404


def test_cannot_escape_the_static_dir(client: TestClient) -> None:
    res = client.get("/%2e%2e/secret.txt")
    assert "secret" not in res.text


def test_missing_index_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        mount_frontend(FastAPI(), tmp_path)


def test_missing_asset_is_404_not_html(client: TestClient) -> None:
    assert client.get("/assets/missing.js").status_code == 404
