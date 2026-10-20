import logging

from app.clients.prowlarr import ProwlarrClient
from app.clients.qbittorrent import QBittorrentClient
from app.models import DownloadStarted, Release
from app.services.release_store import ReleaseStore

logger = logging.getLogger(__name__)

# Marks Kinoarr's torrents so later steps (subtitles) can tell them from the user's other torrents.
KINOARR_TAG = "kinoarr"


class ReleaseNotFoundError(Exception):
    """The release ID is not among Kinoarr's recent search results."""


class DownloadService:
    """Kinoarr's download rules: which link to use and how to mark the torrent."""

    def __init__(
        self,
        release_store: ReleaseStore,
        prowlarr_client: ProwlarrClient,
        qbittorrent_client: QBittorrentClient,
    ) -> None:
        self._release_store = release_store
        self._prowlarr_client = prowlarr_client
        self._qbittorrent_client = qbittorrent_client

    def start_download(self, release_id: str) -> DownloadStarted:
        release = self._release_store.get(release_id)
        if release is None:
            raise ReleaseNotFoundError(f"Release {release_id} not found: search again")

        torrent_source = self._prowlarr_client.fetch_torrent(_preferred_link(release))
        self._qbittorrent_client.add_torrent(torrent_source, tags=[KINOARR_TAG])

        logger.info("Started download of release %s (%r)", release.id, release.title)
        return DownloadStarted(release_id=release.id, title=release.title)


def _preferred_link(release: Release) -> str:
    # A .torrent file lets qBittorrent start at once; a magnet must first fetch metadata from peers.
    # The search only keeps releases with at least one link, so one of the two is set.
    return release.download_url or release.magnet_url
