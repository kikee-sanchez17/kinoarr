from pathlib import Path

import pytest

from app.models import FoundSubtitle, SubtitleStream, Torrent
from app.services.subtitle_detection import (
    DownloadPathMissingError,
    SubtitleDetectionService,
    TorrentNotFinishedError,
    TorrentNotFoundError,
    VideoNotFoundError,
)

HASH = "abc123"


class FakeQBittorrent:
    def __init__(self, torrent: Torrent | None) -> None:
        self._torrent = torrent

    def get_torrent(self, torrent_hash: str) -> Torrent | None:
        return self._torrent


class FakeFfprobe:
    def __init__(self, streams: list[SubtitleStream] | None = None) -> None:
        self._streams = streams or []
        self.probed: list[Path] = []

    def subtitle_streams(self, video_path: Path) -> list[SubtitleStream]:
        self.probed.append(video_path)
        return self._streams


def make_torrent(content_path: Path, progress: float = 1.0) -> Torrent:
    return Torrent(
        hash=HASH,
        name="Movie",
        state="uploading",
        progress=progress,
        size=1_000,
        save_path=str(content_path.parent),
        content_path=str(content_path),
        category="",
        tags=["kinoarr"],
    )


def make_stream(index: int, language: str | None, forced: bool = False) -> SubtitleStream:
    return SubtitleStream(
        index=index, codec="subrip", language=language, title=None, forced=forced, hearing_impaired=False
    )


def service_for(torrent: Torrent | None, ffprobe: FakeFfprobe | None = None) -> SubtitleDetectionService:
    return SubtitleDetectionService(FakeQBittorrent(torrent), ffprobe or FakeFfprobe())


@pytest.fixture
def movie_folder(tmp_path) -> Path:
    folder = tmp_path / "Movie"
    folder.mkdir()
    (folder / "sample.mkv").write_bytes(b"x")
    (folder / "Movie.mkv").write_bytes(b"x" * 100)
    return folder


def test_reports_english_embedded_and_sidecar_subtitles(movie_folder):
    (movie_folder / "Movie.en.srt").write_text("1")
    ffprobe = FakeFfprobe([make_stream(2, "eng"), make_stream(3, "eng", forced=True), make_stream(4, "spa")])

    report = service_for(make_torrent(movie_folder), ffprobe).detect(HASH)

    assert ffprobe.probed == [movie_folder / "Movie.mkv"]
    assert report.video_path == str(movie_folder / "Movie.mkv")
    assert report.torrent_name == "Movie"
    assert report.has_english_subtitle
    assert report.english_subtitles == [
        FoundSubtitle(source="embedded", description="track 2 (subrip, eng)"),
        FoundSubtitle(source="sidecar", description="Movie.en.srt"),
    ]


def test_reports_missing_english_subtitle(movie_folder):
    (movie_folder / "Movie.srt").write_text("1")

    report = service_for(make_torrent(movie_folder), FakeFfprobe([make_stream(2, None)])).detect(HASH)

    assert not report.has_english_subtitle
    assert report.english_subtitles == []


def test_unknown_torrent_raises_not_found():
    with pytest.raises(TorrentNotFoundError):
        service_for(None).detect(HASH)


def test_unfinished_torrent_raises_not_finished(movie_folder):
    with pytest.raises(TorrentNotFinishedError):
        service_for(make_torrent(movie_folder, progress=0.5)).detect(HASH)


def test_missing_path_points_at_path_mapping(tmp_path):
    with pytest.raises(DownloadPathMissingError, match="KINOARR_DOWNLOADS_PATH"):
        service_for(make_torrent(tmp_path / "missing")).detect(HASH)


def test_torrent_without_video_raises_video_not_found(tmp_path):
    (tmp_path / "readme.txt").write_text("1")

    with pytest.raises(VideoNotFoundError):
        service_for(make_torrent(tmp_path)).detect(HASH)
