from fastapi.testclient import TestClient

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
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/config").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_unknown_path_returns_404():
    assert client.get("/does-not-exist").status_code == 404
