from types import SimpleNamespace

from app.clients.qbittorrent import QBittorrentClient


class FakeQBittorrentApi:
    def __init__(self, torrents: list[SimpleNamespace]) -> None:
        self._torrents = torrents

    def torrents_info(self, status_filter: str | None = None) -> list[SimpleNamespace]:
        return self._torrents


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


def client_returning(raw_torrent: SimpleNamespace, remote: str, local: str) -> QBittorrentClient:
    client = QBittorrentClient(
        "http://qbittorrent:8081",
        "admin",
        "secret",
        remote_downloads_path=remote,
        local_downloads_path=local,
    )
    client._client = FakeQBittorrentApi([raw_torrent])
    return client


def test_list_torrents_maps_paths_to_local_folder():
    raw = make_raw_torrent(r"D:\Torrents\Movies", r"D:\Torrents\Movies\Sintel.mkv")
    client = client_returning(raw, remote=r"D:\Torrents", local="/downloads")

    [torrent] = client.list_torrents()

    assert torrent.save_path == "/downloads/Movies"
    assert torrent.content_path == "/downloads/Movies/Sintel.mkv"


def test_list_torrents_keeps_paths_when_mapping_disabled():
    raw = make_raw_torrent("/downloads/Movies", "/downloads/Movies/Sintel.mkv")
    client = client_returning(raw, remote="", local="")

    [torrent] = client.list_torrents()

    assert torrent.save_path == "/downloads/Movies"
    assert torrent.content_path == "/downloads/Movies/Sintel.mkv"
