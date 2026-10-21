from datetime import UTC, datetime

from app.models import Release
from app.services.release_store import ReleaseStore
from app.services.search import SearchService


class FakeProwlarr:
    def __init__(self, releases: list[Release]) -> None:
        self._releases = releases

    def search_movies(self, query: str) -> list[Release]:
        return self._releases


def make_release(release_id: str, seeders: int | None) -> Release:
    return Release(
        id=release_id,
        title=f"Movie {release_id}",
        indexer="Internet Archive",
        size=1_000,
        seeders=seeders,
        leechers=None,
        publish_date=datetime(2020, 1, 1, tzinfo=UTC),
        info_url=None,
        download_url=f"http://prowlarr:9696/1/download?apikey=secret&link={release_id}",
        magnet_url=None,
    )


def test_results_are_sorted_by_seeders_with_unknown_last():
    releases = [make_release("unknown", None), make_release("few", 0), make_release("many", 50)]
    service = SearchService(FakeProwlarr(releases), ReleaseStore())

    results = service.search_movies("night")

    assert [result.id for result in results] == ["many", "few", "unknown"]


def test_releases_are_stored_with_their_download_links():
    store = ReleaseStore()
    release = make_release("a", 5)
    service = SearchService(FakeProwlarr([release]), store)

    service.search_movies("night")

    assert store.get("a") == release


def test_results_have_no_download_links():
    service = SearchService(FakeProwlarr([make_release("a", 5)]), ReleaseStore())

    [result] = service.search_movies("night")

    assert "download_url" not in result.model_dump()
    assert "magnet_url" not in result.model_dump()
