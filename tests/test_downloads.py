import pytest
from fastapi.testclient import TestClient

from app.clients.ffprobe import FfprobeError
from app.clients.prowlarr import ProwlarrError
from app.clients.qbittorrent import QBittorrentError, QBittorrentRejectedError
from app.dependencies import get_download_service, get_qbittorrent_client, get_subtitle_detection_service
from app.main import app
from app.models import DownloadStarted, FoundSubtitle, SubtitleReport, Torrent
from app.services.downloads import ReleaseNotFoundError
from app.services.subtitle_detection import (
    DownloadPathMissingError,
    TorrentNotFinishedError,
    TorrentNotFoundError,
    VideoNotFoundError,
)


class FakeQBittorrent:
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
        save_path="/downloads/movies",
        content_path=f"/downloads/movies/{name}",
        category="",
        tags=[],
    )


def client_with(fake: FakeQBittorrent) -> TestClient:
    app.dependency_overrides[get_qbittorrent_client] = lambda: fake
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_status_ok():
    r = client_with(FakeQBittorrent()).get("/api/downloads/status")
    assert r.status_code == 200
    assert r.json() == {"connected": True, "qbittorrent_version": "v5.0.0"}


def test_list_all_and_completed():
    fake = FakeQBittorrent([make_torrent("Sintel", 1.0), make_torrent("BigBuckBunny", 0.4)])
    c = client_with(fake)

    assert len(c.get("/api/downloads").json()) == 2

    completed = c.get("/api/downloads", params={"completed": True}).json()
    assert [t["name"] for t in completed] == ["Sintel"]


def test_qbittorrent_error_returns_502():
    c = client_with(FakeQBittorrent(error=QBittorrentError("connection refused")))
    r = c.get("/api/downloads")
    assert r.status_code == 502
    assert "connection refused" in r.json()["detail"]

class FakeDownloadService:
    def __init__(self, error=None):
        self._error = error

    def start_download(self, release_id: str) -> DownloadStarted:
        if self._error:
            raise self._error
        return DownloadStarted(release_id=release_id, title="Night of the Living Dead")


def download_client_with(fake: FakeDownloadService) -> TestClient:
    app.dependency_overrides[get_download_service] = lambda: fake
    return TestClient(app)


def test_start_download_returns_202():
    r = download_client_with(FakeDownloadService()).post("/api/downloads", json={"release_id": "abc"})

    assert r.status_code == 202
    assert r.json() == {"release_id": "abc", "title": "Night of the Living Dead"}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ReleaseNotFoundError("Release abc not found: search again"), 404),
        (QBittorrentRejectedError("qBittorrent refused the torrent"), 409),
        (QBittorrentError("Cannot connect to qBittorrent"), 502),
        (ProwlarrError("Cannot connect to Prowlarr at http://prowlarr:9696"), 502),
    ],
)
def test_start_download_errors(error, expected_status):
    r = download_client_with(FakeDownloadService(error=error)).post("/api/downloads", json={"release_id": "abc"})

    assert r.status_code == expected_status
    assert r.json()["detail"] == str(error)


@pytest.mark.parametrize("body", [{"release_id": ""}, {}])
def test_start_download_without_release_id_returns_422(body):
    assert download_client_with(FakeDownloadService()).post("/api/downloads", json=body).status_code == 422


class FakeDetectionService:
    def __init__(self, error=None):
        self._error = error

    def detect(self, torrent_hash: str) -> SubtitleReport:
        if self._error:
            raise self._error
        return SubtitleReport(
            torrent_hash=torrent_hash,
            video_path="/downloads/Movie/Movie.mkv",
            has_english_subtitle=True,
            english_subtitles=[FoundSubtitle(source="sidecar", description="Movie.en.srt")],
        )


def detection_client_with(fake: FakeDetectionService) -> TestClient:
    app.dependency_overrides[get_subtitle_detection_service] = lambda: fake
    return TestClient(app)


def test_detect_subtitles_returns_report():
    r = detection_client_with(FakeDetectionService()).get("/api/downloads/abc/subtitles")

    assert r.status_code == 200
    assert r.json()["has_english_subtitle"] is True
    assert r.json()["english_subtitles"] == [{"source": "sidecar", "description": "Movie.en.srt"}]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (TorrentNotFoundError("No torrent with hash abc"), 404),
        (TorrentNotFinishedError("not finished"), 409),
        (VideoNotFoundError("no video"), 422),
        (DownloadPathMissingError("check KINOARR_DOWNLOADS_PATH"), 500),
        (FfprobeError("ffprobe not found: install ffmpeg"), 500),
        (QBittorrentError("Cannot connect to qBittorrent"), 502),
    ],
)
def test_detect_subtitles_errors(error, expected_status):
    r = detection_client_with(FakeDetectionService(error=error)).get("/api/downloads/abc/subtitles")

    assert r.status_code == expected_status
    assert r.json()["detail"] == str(error)
