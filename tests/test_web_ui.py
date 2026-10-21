import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app.main import app

client = TestClient(app)


def test_root_serves_the_web_ui():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Kinoarr</title>" in response.text


def test_web_ui_assets_are_served():
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200


def test_api_routes_are_not_shadowed_by_the_web_ui():
    assert client.get("/health").status_code == 200
    assert client.get("/api/config").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_unknown_path_returns_404():
    assert client.get("/does-not-exist").status_code == 404


def test_health_reports_the_version():
    assert client.get("/health").json() == {"status": "ok", "version": APP_VERSION}


def test_page_has_a_version_footer():
    assert 'id="app-version"' in client.get("/").text


@pytest.mark.parametrize("path", ["/", "/app.js", "/style.css"])
def test_page_files_must_be_revalidated(path):
    first = client.get(path)
    unchanged = client.get(path, headers={"If-None-Match": first.headers["etag"]})

    assert first.headers["cache-control"] == "no-cache"
    assert unchanged.status_code == 304
    assert unchanged.headers["cache-control"] == "no-cache"


def test_api_answers_are_not_marked_by_the_static_files():
    assert "cache-control" not in client.get("/health").headers
