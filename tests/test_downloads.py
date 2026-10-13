from fastapi.testclient import TestClient

from app.clients.qbittorrent import QBittorrentError
from app.dependencies import get_qbit_client
from app.main import app
from app.models import Torrent


class FakeQBit:
    def __init__(self, torrents=None, error=None):
        self._torrents = torrents or []
        self._error = error

    def version(self) -> str:
        if self._error:
            raise self._error
        return "v5.0.0"

    def list_torrents(self, completed_only: bool = False) -> list[Torrent]:
        if self._error:
            raise self._error
        if completed_only:
            return [t for t in self._torrents if t.progress >= 1.0]
        return self._torrents


def make_torrent(name: str, progress: float) -> Torrent:
    return Torrent(
        hash=name.lower(),
        name=name,
        state="uploading" if progress >= 1.0 else "downloading",
        progress=progress,
        size=1_000,
        save_path="/downloads/peliculas",
        content_path=f"/downloads/peliculas/{name}",
        category="",
        tags=[],
    )


def client_with(fake: FakeQBit) -> TestClient:
    app.dependency_overrides[get_qbit_client] = lambda: fake
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_status_ok():
    r = client_with(FakeQBit()).get("/api/downloads/status")
    assert r.status_code == 200
    assert r.json() == {"connected": True, "qbittorrent_version": "v5.0.0"}


def test_list_all_and_completed():
    fake = FakeQBit([make_torrent("Sintel", 1.0), make_torrent("BigBuckBunny", 0.4)])
    c = client_with(fake)

    assert len(c.get("/api/downloads").json()) == 2

    completed = c.get("/api/downloads", params={"completed": True}).json()
    assert [t["name"] for t in completed] == ["Sintel"]


def test_qbit_error_returns_502():
    c = client_with(FakeQBit(error=QBittorrentError("sin conexión")))
    r = c.get("/api/downloads")
    assert r.status_code == 502
    assert "sin conexión" in r.json()["detail"]