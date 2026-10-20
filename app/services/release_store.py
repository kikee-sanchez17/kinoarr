import threading
from collections import OrderedDict

from app.models import Release

MAX_STORED_RELEASES = 1000


class ReleaseStore:
    """In-memory store of recent search results, so download links never leave the server.

    Bounded: once full, the oldest releases are evicted first.
    """

    def __init__(self, max_releases: int = MAX_STORED_RELEASES) -> None:
        self._max_releases = max_releases
        self._releases: OrderedDict[str, Release] = OrderedDict()
        # FastAPI runs sync routes in a thread pool, so concurrent searches can add at once.
        self._lock = threading.Lock()

    def add(self, releases: list[Release]) -> None:
        with self._lock:
            for release in releases:
                self._releases[release.id] = release
                self._releases.move_to_end(release.id)
            while len(self._releases) > self._max_releases:
                self._releases.popitem(last=False)

    def get(self, release_id: str) -> Release | None:
        with self._lock:
            return self._releases.get(release_id)
