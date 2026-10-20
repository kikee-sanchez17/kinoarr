from pathlib import Path

import pytest

from app.models import SubtitleStream
from app.subtitles import english_sidecars, find_main_video, is_english_embedded, is_english_sidecar


def make_stream(language: str | None = "eng", title: str | None = None, forced=False, hearing_impaired=False):
    return SubtitleStream(
        index=2,
        codec="subrip",
        language=language,
        title=title,
        forced=forced,
        hearing_impaired=hearing_impaired,
    )


def write_file(path: Path, size: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


@pytest.mark.parametrize(
    "subtitle_name",
    ["Movie.en.srt", "Movie.eng.ass", "Movie.EN.srt", "Movie.en.default.srt", "Movie.en.vtt", "Movie.en.SSA"],
)
def test_english_sidecars_match(subtitle_name):
    assert is_english_sidecar(subtitle_name, "Movie")


@pytest.mark.parametrize(
    "subtitle_name",
    [
        "Movie.srt",  # no language tag: unknown
        "Movie.en.forced.srt",
        "Movie.en.sdh.srt",
        "Movie.en.hi.srt",
        "Movie.en.cc.vtt",
        "Movie.es.srt",
        "Movie.en.txt",
        "Movie.en.sub",
        "Other.en.srt",
        "Movie 2.en.srt",  # a different movie whose name starts the same
        "Movie.2.en.srt.bak",
    ],
)
def test_non_english_or_ignored_sidecars_do_not_match(subtitle_name):
    assert not is_english_sidecar(subtitle_name, "Movie")


@pytest.mark.parametrize("language", ["eng", "en", "ENG"])
def test_english_embedded_tracks_count(language):
    assert is_english_embedded(make_stream(language=language))


@pytest.mark.parametrize(
    "stream",
    [
        make_stream(forced=True),
        make_stream(hearing_impaired=True),
        make_stream(title="English SDH"),
        make_stream(language=None),
        make_stream(language="spa"),
    ],
)
def test_forced_sdh_untagged_and_other_languages_do_not_count(stream):
    assert not is_english_embedded(stream)


def test_find_main_video_returns_single_video_file(tmp_path):
    movie = write_file(tmp_path / "Movie.mkv")

    assert find_main_video(movie) == movie


def test_find_main_video_ignores_single_non_video_file(tmp_path):
    assert find_main_video(write_file(tmp_path / "Movie.iso")) is None


def test_find_main_video_picks_largest_video_in_nested_folders(tmp_path):
    write_file(tmp_path / "Sample" / "sample.mkv", size=10)
    write_file(tmp_path / "big-but-not-video.iso", size=1_000)
    movie = write_file(tmp_path / "Movie" / "Movie.MKV", size=100)

    assert find_main_video(tmp_path) == movie


def test_find_main_video_returns_none_without_videos(tmp_path):
    write_file(tmp_path / "readme.txt")

    assert find_main_video(tmp_path) is None


def test_english_sidecars_only_looks_beside_the_video(tmp_path):
    movie = write_file(tmp_path / "Movie.mkv")
    beside = write_file(tmp_path / "Movie.en.srt")
    write_file(tmp_path / "Movie.es.srt")
    write_file(tmp_path / "Subs" / "Movie.en.srt")

    assert english_sidecars(movie) == [beside]
