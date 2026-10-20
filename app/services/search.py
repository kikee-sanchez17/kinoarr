from app.clients.prowlarr import ProwlarrClient
from app.models import Release, SearchResult
from app.services.release_store import ReleaseStore

DOWNLOAD_LINK_FIELDS = {"download_url", "magnet_url"}


class SearchService:
    """Kinoarr's search rules: sort releases, keep their links server-side, return them without links."""

    def __init__(self, prowlarr_client: ProwlarrClient, release_store: ReleaseStore) -> None:
        self._prowlarr_client = prowlarr_client
        self._release_store = release_store

    def search_movies(self, query: str) -> list[SearchResult]:
        releases = sorted(self._prowlarr_client.search_movies(query), key=_most_seeders_first)
        self._release_store.add(releases)
        return [_without_download_links(release) for release in releases]


def _most_seeders_first(release: Release) -> tuple[bool, int]:
    # Unknown seeders sort after every known count, including zero.
    return (release.seeders is None, -(release.seeders or 0))


def _without_download_links(release: Release) -> SearchResult:
    return SearchResult(**release.model_dump(exclude=DOWNLOAD_LINK_FIELDS))
