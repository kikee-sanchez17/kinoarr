from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.clients.prowlarr import ProwlarrError
from app.dependencies import get_search_service
from app.main import app
from app.models import SearchResult


class FakeSearchService:
    def __init__(self, results=None, error=None):
        self._results = results or []
        self._error = error

    def search_movies(self, query: str) -> list[SearchResult]:
        if self._error:
            raise self._error
        return self._results


def make_result(title: str) -> SearchResult:
    return SearchResult(
        id="0123456789abcdef",
        title=title,
        indexer="Internet Archive",
        size=1_000,
        seeders=5,
        leechers=1,
        publish_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        info_url="https://archive.org/details/night",
    )


def client_with(fake: FakeSearchService) -> TestClient:
    app.dependency_overrides[get_search_service] = lambda: fake
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_search_returns_results_without_download_links():
    c = client_with(FakeSearchService([make_result("Night of the Living Dead")]))

    r = c.get("/api/search", params={"query": "night"})

    assert r.status_code == 200
    [result] = r.json()
    assert result["title"] == "Night of the Living Dead"
    assert "download_url" not in result
    assert "magnet_url" not in result
    assert "apikey" not in r.text


def test_prowlarr_error_returns_502():
    c = client_with(FakeSearchService(error=ProwlarrError("Cannot connect to Prowlarr at http://prowlarr:9696")))

    r = c.get("/api/search", params={"query": "night"})

    assert r.status_code == 502
    assert "Cannot connect to Prowlarr" in r.json()["detail"]


def test_empty_query_returns_422():
    c = client_with(FakeSearchService())

    assert c.get("/api/search", params={"query": ""}).status_code == 422
    assert c.get("/api/search").status_code == 422
