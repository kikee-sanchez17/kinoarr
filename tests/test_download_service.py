from datetime import datetime, timezone

import pytest

from app.models import Release, TorrentFile, TorrentSource
from app.services.downloads import KINOARR_TAG, DownloadService, ReleaseNotFoundError
from app.services.release_store import ReleaseStore

DOWNLOAD_URL = "http://prowlarr:9696/1/download?apikey=secret&link=abc"
MAGNET_URL = "http://prowlarr:9696/1/magnet?apikey=secret&link=abc"


class FakeProwlarr:
    def __init__(self) -> None:
        self.fetched_links: list[str] = []

    def fetch_torrent(self, download_link: str) -> TorrentSource:
        self.fetched_links.append(download_link)
        return TorrentFile(content=b"torrent")


class FakeQBittorrent:
    def __init__(self) -> None:
        self.added: list[tuple[TorrentSource, list[str]]] = []

    def add_torrent(self, source: TorrentSource, tags: list[str]) -> None:
        self.added.append((source, tags))


def make_release(download_url: str | None, magnet_url: str | None) -> Release:
    return Release(
        id="0123456789abcdef",
        title="Night of the Living Dead",
        indexer="Internet Archive",
        size=1_000,
        seeders=5,
        leechers=1,
        publish_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        info_url=None,
        download_url=download_url,
        magnet_url=magnet_url,
    )


def service_with(release: Release | None) -> tuple[DownloadService, FakeProwlarr, FakeQBittorrent]:
    store = ReleaseStore()
    if release:
        store.add([release])
    prowlarr, qbittorrent = FakeProwlarr(), FakeQBittorrent()
    return DownloadService(store, prowlarr, qbittorrent), prowlarr, qbittorrent


def test_unknown_release_raises_not_found():
    service, _, _ = service_with(None)

    with pytest.raises(ReleaseNotFoundError):
        service.start_download("missing")


def test_download_url_is_preferred_over_magnet():
    service, prowlarr, _ = service_with(make_release(DOWNLOAD_URL, MAGNET_URL))

    service.start_download("0123456789abcdef")

    assert prowlarr.fetched_links == [DOWNLOAD_URL]


def test_magnet_url_is_used_when_it_is_the_only_link():
    service, prowlarr, _ = service_with(make_release(None, MAGNET_URL))

    service.start_download("0123456789abcdef")

    assert prowlarr.fetched_links == [MAGNET_URL]


def test_torrent_is_added_with_kinoarr_tag():
    service, _, qbittorrent = service_with(make_release(DOWNLOAD_URL, None))

    started = service.start_download("0123456789abcdef")

    assert qbittorrent.added == [(TorrentFile(content=b"torrent"), [KINOARR_TAG])]
    assert started.release_id == "0123456789abcdef"
    assert started.title == "Night of the Living Dead"
