from types import SimpleNamespace

import pytest
import qbittorrentapi
from qbittorrentapi.torrents import TorrentsAddedMetadata

from app.clients.qbittorrent import QBittorrentClient, QBittorrentError, QBittorrentRejectedError
from app.models import MagnetLink, TorrentFile


class FakeQBittorrentApi:
    def __init__(self, torrents: list[SimpleNamespace] | None = None, add_response="Ok.", error=None) -> None:
        self._torrents = torrents or []
        self._add_response = add_response
        self._error = error
        self.added: list[dict] = []

    def torrents_info(self, status_filter: str | None = None, torrent_hashes: str | None = None):
        if self._error:
            raise self._error
        if torrent_hashes is not None:
            return [t for t in self._torrents if t.hash == torrent_hashes]
        return self._torrents

    def torrents_add(self, **kwargs):
        if self._error:
            raise self._error
        self.added.append(kwargs)
        return self._add_response


def make_raw_torrent(save_path: str, content_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        hash="abc",
        name="Sintel",
        state="uploading",
        progress=1.0,
        size=1_000,
        save_path=save_path,
        content_path=content_path,
        category="",
        tags="",
    )


def client_using(fake_api: FakeQBittorrentApi, remote: str = "", local: str = "") -> QBittorrentClient:
    client = QBittorrentClient(
        "http://qbittorrent:8081",
        "admin",
        "secret",
        remote_downloads_path=remote,
        local_downloads_path=local,
    )
    client._client = fake_api
    return client


def test_list_torrents_maps_paths_to_local_folder():
    raw = make_raw_torrent(r"D:\Torrents\Movies", r"D:\Torrents\Movies\Sintel.mkv")
    client = client_using(FakeQBittorrentApi([raw]), remote=r"D:\Torrents", local="/downloads")

    [torrent] = client.list_torrents()

    assert torrent.save_path == "/downloads/Movies"
    assert torrent.content_path == "/downloads/Movies/Sintel.mkv"


def test_list_torrents_keeps_paths_when_mapping_disabled():
    raw = make_raw_torrent("/downloads/Movies", "/downloads/Movies/Sintel.mkv")
    client = client_using(FakeQBittorrentApi([raw]))

    [torrent] = client.list_torrents()

    assert torrent.save_path == "/downloads/Movies"
    assert torrent.content_path == "/downloads/Movies/Sintel.mkv"


def test_get_torrent_returns_mapped_torrent():
    raw = make_raw_torrent(r"D:\Torrents\Movies", r"D:\Torrents\Movies\Sintel.mkv")
    client = client_using(FakeQBittorrentApi([raw]), remote=r"D:\Torrents", local="/downloads")

    torrent = client.get_torrent("abc")

    assert torrent is not None
    assert torrent.content_path == "/downloads/Movies/Sintel.mkv"


def test_get_torrent_returns_none_for_unknown_hash():
    assert client_using(FakeQBittorrentApi([])).get_torrent("missing") is None


def test_add_torrent_uploads_torrent_file_with_tags():
    fake_api = FakeQBittorrentApi()

    client_using(fake_api).add_torrent(TorrentFile(content=b"torrent"), tags=["kinoarr"])

    assert fake_api.added == [{"torrent_files": b"torrent", "tags": ["kinoarr"]}]


def test_add_torrent_passes_magnet_link_as_url():
    fake_api = FakeQBittorrentApi()

    client_using(fake_api).add_torrent(MagnetLink(uri="magnet:?xt=urn:btih:abc"), tags=["kinoarr"])

    assert fake_api.added == [{"urls": "magnet:?xt=urn:btih:abc", "tags": ["kinoarr"]}]


@pytest.mark.parametrize(
    "add_response",
    ["Ok.", TorrentsAddedMetadata({"success_count": 1, "failure_count": 0})],
)
def test_add_torrent_accepts_success_responses(add_response):
    client_using(FakeQBittorrentApi(add_response=add_response)).add_torrent(TorrentFile(content=b"t"), tags=[])


@pytest.mark.parametrize(
    "fake_api",
    [
        FakeQBittorrentApi(add_response="Fails."),
        FakeQBittorrentApi(add_response=TorrentsAddedMetadata({"success_count": 0, "failure_count": 1})),
        FakeQBittorrentApi(error=qbittorrentapi.Conflict409Error("already added")),
    ],
)
def test_add_torrent_rejections_raise_rejected_error(fake_api):
    with pytest.raises(QBittorrentRejectedError):
        client_using(fake_api).add_torrent(TorrentFile(content=b"t"), tags=[])


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (qbittorrentapi.LoginFailed(), "login failed"),
        (qbittorrentapi.APIConnectionError("refused"), "Cannot connect"),
    ],
)
def test_add_torrent_connection_errors_raise_qbittorrent_error(error, expected_message):
    client = client_using(FakeQBittorrentApi(error=error))

    with pytest.raises(QBittorrentError, match=expected_message) as exc_info:
        client.add_torrent(TorrentFile(content=b"t"), tags=[])

    assert not isinstance(exc_info.value, QBittorrentRejectedError)
