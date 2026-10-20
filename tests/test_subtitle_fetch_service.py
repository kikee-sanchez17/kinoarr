from pathlib import Path

import pytest

from app.models import SubtitleCandidate, SubtitleReport
from app.movie_hash import CHUNK_SIZE
from app.services.subtitle_fetch import (
    SubtitleDownloadsDisabledError,
    SubtitleFetchService,
    SubtitleNotFoundError,
    SubtitleWriteError,
)

HASH = "abc123"
SUBTITLE = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n"


class FakeDetection:
    def __init__(self, video_path: Path, has_english_subtitle: bool = False) -> None:
        self._video_path = video_path
        self._has_english_subtitle = has_english_subtitle

    def detect(self, torrent_hash: str) -> SubtitleReport:
        return SubtitleReport(
            torrent_hash=torrent_hash,
            torrent_name="Movie.1968.1080p",
            video_path=str(self._video_path),
            has_english_subtitle=self._has_english_subtitle,
            english_subtitles=[],
        )


class FakeOpenSubtitles:
    def __init__(self, by_hash=None, by_name=None) -> None:
        self._by_hash = by_hash or []
        self._by_name = by_name or []
        self.searches: list[dict] = []
        self.downloaded: list[int] = []

    def search_english(self, movie_hash=None, query=None) -> list[SubtitleCandidate]:
        self.searches.append({"movie_hash": movie_hash, "query": query})
        return self._by_hash if movie_hash else self._by_name

    def download(self, file_id: int) -> bytes:
        self.downloaded.append(file_id)
        return SUBTITLE


def make_candidate(file_id: int, hash_match: bool = False) -> SubtitleCandidate:
    return SubtitleCandidate(file_id=file_id, file_name="Movie.srt", download_count=10, hash_match=hash_match)


@pytest.fixture
def video(tmp_path) -> Path:
    path = tmp_path / "Movie.1968.1080p.mkv"
    path.write_bytes(bytes(2 * CHUNK_SIZE))  # big enough to have a hash
    return path


def test_already_present_does_not_search(video):
    opensubtitles = FakeOpenSubtitles()
    service = SubtitleFetchService(FakeDetection(video, has_english_subtitle=True), opensubtitles)

    result = service.fetch(HASH)

    assert result.status == "already_present"
    assert opensubtitles.searches == []


def test_hash_search_comes_first_and_subtitle_is_saved_beside_video(video):
    opensubtitles = FakeOpenSubtitles(by_hash=[make_candidate(7, hash_match=True)])
    service = SubtitleFetchService(FakeDetection(video), opensubtitles)

    result = service.fetch(HASH)

    assert opensubtitles.searches == [{"movie_hash": f"{2 * CHUNK_SIZE:016x}", "query": None}]
    assert opensubtitles.downloaded == [7]
    assert result.status == "downloaded"
    assert result.subtitle_file == "Movie.1968.1080p.en.srt"
    assert (video.parent / "Movie.1968.1080p.en.srt").read_bytes() == SUBTITLE
    assert not list(video.parent.glob("*.part"))


def test_name_search_is_the_fallback(video):
    opensubtitles = FakeOpenSubtitles(by_name=[make_candidate(9)])

    SubtitleFetchService(FakeDetection(video), opensubtitles).fetch(HASH)

    assert opensubtitles.searches[-1] == {"movie_hash": None, "query": "Movie.1968.1080p"}
    assert opensubtitles.downloaded == [9]


def test_small_file_goes_straight_to_name_search(tmp_path):
    small_video = tmp_path / "Movie.mkv"
    small_video.write_bytes(b"x")
    opensubtitles = FakeOpenSubtitles(by_name=[make_candidate(9)])

    SubtitleFetchService(FakeDetection(small_video), opensubtitles).fetch(HASH)

    assert opensubtitles.searches == [{"movie_hash": None, "query": "Movie.1968.1080p"}]


def test_nothing_found_raises_not_found(video):
    with pytest.raises(SubtitleNotFoundError, match="Movie.1968.1080p"):
        SubtitleFetchService(FakeDetection(video), FakeOpenSubtitles()).fetch(HASH)


def test_without_client_downloads_are_disabled(video):
    with pytest.raises(SubtitleDownloadsDisabledError, match="OPENSUBTITLES_API_KEY"):
        SubtitleFetchService(FakeDetection(video), None).fetch(HASH)


def test_write_failure_mentions_permissions_and_leaves_no_partial_file(video, monkeypatch):
    def refuse_rename(self, target):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "replace", refuse_rename)
    opensubtitles = FakeOpenSubtitles(by_hash=[make_candidate(7)])

    with pytest.raises(SubtitleWriteError, match="PUID/PGID"):
        SubtitleFetchService(FakeDetection(video), opensubtitles).fetch(HASH)

    assert sorted(path.name for path in video.parent.iterdir()) == [video.name]
