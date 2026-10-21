import logging
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
from tests.subtitle_samples import ENGLISH_SRT, SPANISH_SRT

HASH = "abc123"
SUBTITLE = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n"


class FakeDetection:
    def __init__(self, video_path: Path, has_english_subtitle: bool = False, bundled: list[Path] | None = None) -> None:
        self._video_path = video_path
        self._has_english_subtitle = has_english_subtitle
        self._bundled = bundled or []

    def bundled_subtitles(self, torrent_hash: str) -> list[Path]:
        return self._bundled

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


def make_candidate(
    file_id: int, hash_match: bool = False, movie_title: str = "Movie", movie_year: int = 1968, download_count: int = 10
) -> SubtitleCandidate:
    return SubtitleCandidate(
        file_id=file_id,
        file_name="Movie.srt",
        download_count=download_count,
        hash_match=hash_match,
        movie_title=movie_title,
        movie_year=movie_year,
    )


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


def write_subtitle(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_english_subtitle_in_the_torrent_is_copied_without_opensubtitles(video):
    bundled = write_subtitle(video.parent / "Subs" / "English.srt", ENGLISH_SRT)
    opensubtitles = FakeOpenSubtitles(by_hash=[make_candidate(7, hash_match=True)])

    result = SubtitleFetchService(FakeDetection(video, bundled=[bundled]), opensubtitles).fetch(HASH)

    assert result.status == "copied_from_torrent"
    assert result.subtitle_file == "Movie.1968.1080p.en.srt"
    assert (video.parent / "Movie.1968.1080p.en.srt").read_bytes() == bundled.read_bytes()
    assert bundled.exists()  # copied, not moved: qBittorrent keeps seeding it
    assert opensubtitles.searches == []


def test_copy_keeps_the_subtitle_format(video):
    bundled = write_subtitle(video.parent / "Movie.1968.1080p.ASS", ENGLISH_SRT)

    result = SubtitleFetchService(FakeDetection(video, bundled=[bundled]), None).fetch(HASH)

    assert result.subtitle_file == "Movie.1968.1080p.en.ass"


def test_copy_works_without_opensubtitles(video):
    bundled = write_subtitle(video.parent / "Movie.1968.1080p.srt", ENGLISH_SRT)

    result = SubtitleFetchService(FakeDetection(video, bundled=[bundled]), None).fetch(HASH)

    assert result.status == "copied_from_torrent"


def test_non_english_subtitle_in_the_torrent_falls_through_to_opensubtitles(video):
    spanish = write_subtitle(video.parent / "Movie.1968.1080p.srt", SPANISH_SRT)
    opensubtitles = FakeOpenSubtitles(by_hash=[make_candidate(7, hash_match=True)])

    result = SubtitleFetchService(FakeDetection(video, bundled=[spanish]), opensubtitles).fetch(HASH)

    assert result.status == "downloaded"
    assert opensubtitles.downloaded == [7]


def test_first_english_one_is_used_when_several_are_bundled(video):
    spanish = write_subtitle(video.parent / "Subs" / "Spanish.srt", SPANISH_SRT)
    english = write_subtitle(video.parent / "Subs" / "English.srt", ENGLISH_SRT)

    SubtitleFetchService(FakeDetection(video, bundled=[spanish, english]), None).fetch(HASH)

    assert (video.parent / "Movie.1968.1080p.en.srt").read_text(encoding="utf-8") == ENGLISH_SRT


def test_hash_match_for_another_movie_is_skipped_for_a_name_match(video, caplog):
    wrong_movie = make_candidate(1, hash_match=True, movie_title="Before I Fall", movie_year=2017, download_count=999)
    opensubtitles = FakeOpenSubtitles(by_hash=[wrong_movie, wrong_movie], by_name=[make_candidate(9)])

    with caplog.at_level(logging.INFO):
        SubtitleFetchService(FakeDetection(video), opensubtitles).fetch(HASH)

    assert opensubtitles.downloaded == [9]
    [skipped] = [record.message for record in caplog.records if "Skipped" in record.message]
    assert skipped == "Skipped OpenSubtitles results for other movies than 'Movie.1968.1080p': Before I Fall (2017)"


def test_popular_hash_match_for_another_movie_does_not_beat_the_right_one(video):
    wrong_movie = make_candidate(1, hash_match=True, movie_title="Before I Fall", movie_year=2017, download_count=999)
    right_movie = make_candidate(2, hash_match=True, download_count=5)
    opensubtitles = FakeOpenSubtitles(by_hash=[wrong_movie, right_movie])

    SubtitleFetchService(FakeDetection(video), opensubtitles).fetch(HASH)

    assert opensubtitles.downloaded == [2]


def test_only_other_movies_found_raises_not_found(video):
    other = make_candidate(1, movie_title="Another Movie", movie_year=1968)
    opensubtitles = FakeOpenSubtitles(by_hash=[other], by_name=[other])

    with pytest.raises(SubtitleNotFoundError):
        SubtitleFetchService(FakeDetection(video), opensubtitles).fetch(HASH)

    assert opensubtitles.downloaded == []
