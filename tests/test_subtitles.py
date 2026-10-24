from pathlib import Path

import pytest

from app.models import DownloadDetails, SubtitleCandidate, SubtitleStream
from app.subtitles import (
    best_candidate,
    bundled_subtitles,
    english_sidecar_path,
    english_sidecars,
    find_main_video,
    frame_rate_fit,
    is_english_embedded,
    is_english_sidecar,
    looks_english,
    matches_movie,
    read_subtitle_text,
)
from tests.subtitle_samples import ENGLISH_LINES, ENGLISH_SRT, FRENCH_SRT, SPANISH_SRT, to_srt


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


def make_candidate(
    file_id: int,
    download_count: int,
    hash_match: bool = False,
    release_name: str | None = None,
    frame_rate: float | None = None,
) -> SubtitleCandidate:
    return SubtitleCandidate(
        file_id=file_id,
        file_name=f"{file_id}.srt",
        download_count=download_count,
        hash_match=hash_match,
        release_name=release_name,
        frame_rate=frame_rate,
    )


UNKNOWN_DOWNLOAD = DownloadDetails(names=["Movie (1968)"], frame_rate=None)
LADY_BIRD_DOWNLOAD = DownloadDetails(
    names=["Lady Bird (2017) [BluRay] [1080p] [YTS.AM]", "Lady.Bird.2017.1080p.BluRay.x264-[YTS.AM]"],
    frame_rate=24000 / 1001,
)


def test_english_sidecar_path_is_recognised_as_english_sidecar():
    video = Path("/downloads/Movie (1968)/Movie.1968.1080p.mkv")

    sidecar = english_sidecar_path(video)

    assert sidecar == Path("/downloads/Movie (1968)/Movie.1968.1080p.en.srt")
    assert is_english_sidecar(sidecar.name, video.stem)


def test_best_candidate_prefers_hash_match_over_downloads():
    candidates = [make_candidate(1, 10_000), make_candidate(2, 5, hash_match=True), make_candidate(3, 50)]

    assert best_candidate(candidates, UNKNOWN_DOWNLOAD).file_id == 2


def test_best_candidate_without_hash_match_picks_most_downloaded():
    assert best_candidate([make_candidate(1, 10), make_candidate(2, 50)], UNKNOWN_DOWNLOAD).file_id == 2


def test_best_candidate_of_nothing_is_none():
    assert best_candidate([], UNKNOWN_DOWNLOAD) is None


def test_best_candidate_for_lady_bird_skips_the_popular_screener():
    # The top results of a real OpenSubtitles name search for "lady bird 2017" (2026-10-24).
    candidates = [
        make_candidate(1, 85349, release_name="Lady Bird 2017 DVDScr XVID AC3 HQ Hive-CM8", frame_rate=30.0),
        make_candidate(2, 84740, release_name="Lady.Bird.2017.720p.WEB-DL.DD5.1.H264-FGT", frame_rate=23.976),
        make_candidate(3, 75342, release_name="Lady.Bird.2017.720p.BluRay.x264.DTS-HDC", frame_rate=23.976),
        make_candidate(4, 28062, release_name="Lady.Bird.2017.1080p.BluRay.x264.DTS-HDC", frame_rate=23.976),
        make_candidate(5, 21586, release_name="Lady.Bird.2017.720p.BluRay.x264-GECKOS", frame_rate=23.976),
        make_candidate(6, 20053, release_name="Lady.Bird.2017.DVDScr.XVID.AC3.HQ.Hive-CM8", frame_rate=30.0),
        make_candidate(7, 9619, release_name="Lady.Bird.2017.720p.WEB-DL.DD5.1.H264-FGT", frame_rate=None),
        make_candidate(8, 6584, release_name="Lady Bird (2017)", frame_rate=None),
    ]

    assert best_candidate(candidates, LADY_BIRD_DOWNLOAD).file_id == 3


def test_best_candidate_hash_match_beats_every_other_rule():
    candidates = [
        make_candidate(1, 5, hash_match=True, release_name="Lady Bird 2017 DVDScr", frame_rate=30.0),
        make_candidate(2, 90000, release_name="Lady.Bird.2017.1080p.BluRay.x264-[YTS.AM]", frame_rate=23.976),
    ]

    assert best_candidate(candidates, LADY_BIRD_DOWNLOAD).file_id == 1


def test_best_candidate_puts_pre_release_last():
    candidates = [
        make_candidate(1, 90000, release_name="Movie.2017.HDCAM", frame_rate=23.976),
        make_candidate(2, 10, release_name="Movie.2017.HDTV", frame_rate=25.0),
    ]

    assert best_candidate(candidates, LADY_BIRD_DOWNLOAD).file_id == 2


def test_best_candidate_pre_release_fits_a_pre_release_download():
    screener_download = DownloadDetails(names=["Movie 2017 DVDScr XviD"], frame_rate=None)
    candidates = [
        make_candidate(1, 10, release_name="Movie.2017.DVDScr.XviD"),
        make_candidate(2, 90000, release_name="Movie.2017.1080p.BluRay"),
    ]

    assert best_candidate(candidates, screener_download).file_id == 1


def test_best_candidate_prefers_the_same_frame_rate():
    candidates = [
        make_candidate(1, 90000, release_name="Movie.2017.1080p.BluRay", frame_rate=25.0),
        make_candidate(2, 10, release_name="Movie.2017.1080p.WEB-DL", frame_rate=23.976),
    ]

    assert best_candidate(candidates, LADY_BIRD_DOWNLOAD).file_id == 2


def test_best_candidate_prefers_the_same_source():
    candidates = [
        make_candidate(1, 90000, release_name="Movie.2017.1080p.WEB-DL", frame_rate=23.976),
        make_candidate(2, 10, release_name="Movie.2017.720p.BRRip", frame_rate=23.976),
    ]

    assert best_candidate(candidates, LADY_BIRD_DOWNLOAD).file_id == 2


def test_best_candidate_prefers_the_same_group():
    candidates = [
        make_candidate(1, 90000, release_name="Movie.2017.1080p.BluRay.x264-SPARKS", frame_rate=23.976),
        make_candidate(2, 10, release_name="Movie.2017.720p.BluRay.x264.YIFY", frame_rate=23.976),
    ]

    assert best_candidate(candidates, LADY_BIRD_DOWNLOAD).file_id == 2


def test_best_candidate_without_video_frame_rate_skips_that_rule():
    download = DownloadDetails(names=LADY_BIRD_DOWNLOAD.names, frame_rate=None)
    candidates = [
        make_candidate(1, 10, release_name="Movie.2017.1080p.BluRay", frame_rate=23.976),
        make_candidate(2, 90000, release_name="Movie.2017.1080p.BluRay", frame_rate=30.0),
    ]

    assert best_candidate(candidates, download).file_id == 2


@pytest.mark.parametrize(
    ("subtitle_frame_rate", "video_frame_rate", "expected"),
    [
        (23.976, 24000 / 1001, 2),
        (25.0, 25.0, 2),
        (25.0, 24000 / 1001, 0),
        (24.0, 24000 / 1001, 0),
        (None, 24000 / 1001, 1),
        (23.976, None, 1),
    ],
)
def test_frame_rate_fit(subtitle_frame_rate, video_frame_rate, expected):
    assert frame_rate_fit(subtitle_frame_rate, video_frame_rate) == expected


def test_english_sidecar_path_keeps_another_format():
    assert english_sidecar_path(Path("/m/Movie.mkv"), ".ass") == Path("/m/Movie.en.ass")


def test_bundled_subtitles_puts_english_names_first_then_larger_files(tmp_path):
    write_file(tmp_path / "Movie.mkv")
    untagged = write_file(tmp_path / "Movie.srt", size=50)
    english = write_file(tmp_path / "Subs" / "2_English.srt", size=10)
    spanish = write_file(tmp_path / "Subs" / "4_Spanish.srt", size=80)
    write_file(tmp_path / "Subs" / "3_English.SDH.srt", size=90)
    write_file(tmp_path / "Movie.en.forced.srt", size=5)
    write_file(tmp_path / "notes.txt")

    assert bundled_subtitles(tmp_path) == [english, spanish, untagged]


def test_single_file_torrent_has_no_bundled_subtitles(tmp_path):
    movie = write_file(tmp_path / "Movie.mkv")
    write_file(tmp_path / "Other movie.srt")

    assert bundled_subtitles(movie) == []


def test_english_dialogue_looks_english():
    assert looks_english(ENGLISH_SRT)


@pytest.mark.parametrize("subtitle_text", [SPANISH_SRT, FRENCH_SRT])
def test_other_languages_do_not_look_english(subtitle_text):
    assert not looks_english(subtitle_text)


@pytest.mark.parametrize(
    "subtitle_text",
    [
        to_srt(ENGLISH_LINES[:3]),  # too little text to judge
        "1\n00:00:01,000 --> 00:00:02,000\n\n" * 200,  # only numbers and timings
        "",
    ],
)
def test_too_little_text_is_not_judged_english(subtitle_text):
    assert not looks_english(subtitle_text)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("Don't go — café".encode("utf-8-sig"), "Don't go — café"),
        ("Don't go — café".encode("utf-16"), "Don't go — café"),
        ("Don't go café".encode("cp1252"), "Don't go café"),
    ],
)
def test_read_subtitle_text_handles_common_encodings(tmp_path, content, expected):
    path = tmp_path / "Movie.srt"
    path.write_bytes(content)

    assert read_subtitle_text(path) == expected


EMILY_ROSE_TORRENT = "The Exorcism of Emily Rose UNRATED (2005) [1080p]"
EMILY_ROSE_VIDEO = "The.Exorcism.of.Emily.Rose.UNRATED.2005.1080p.BrRip.x264.BOKUTOX.YIFY"


@pytest.mark.parametrize(
    ("title", "year", "names"),
    [
        ("The Exorcism of Emily Rose", 2005, [EMILY_ROSE_TORRENT, EMILY_ROSE_VIDEO]),
        ("The Exorcism of Emily Rose", 2005, [EMILY_ROSE_VIDEO]),
        ("The Exorcism of Emily Rose", 2005, ["Exorcism of Emily Rose 2005 720p"]),  # name without "The"
        ("Amélie", 2001, ["Amelie.2001.1080p.BluRay"]),
        ("Fast & Furious", 2009, ["Fast.and.Furious.2009.720p"]),
        ("Wallace &amp; Gromit: The Curse of the Were-Rabbit", 2005, ["Wallace & Gromit The Curse of the Were-Rabbit"]),
        ("Night of the Living Dead", 1968, ["Night of the Living Dead"]),  # no year in the name
        ("Night of the Living Dead", None, ["Night of the Living Dead (1968)"]),
        ("1917", 2019, ["1917 (2019) [1080p]"]),
    ],
)
def test_matching_movies(title, year, names):
    assert matches_movie(title, year, names)


@pytest.mark.parametrize(
    ("title", "year", "names"),
    [
        ("Before I Fall", 2017, [EMILY_ROSE_TORRENT, EMILY_ROSE_VIDEO]),
        ("The Exorcism of God", 2021, [EMILY_ROSE_TORRENT, EMILY_ROSE_VIDEO]),
        ("The Exorcism of Emily Rose", 2004, [EMILY_ROSE_TORRENT]),  # same title, another year
        ("Night of the Living Dead", 1990, ["Night of the Living Dead (1968)"]),
        ("Rose", 2005, ["Rosemary 2005"]),  # whole words only
        (None, 2005, [EMILY_ROSE_TORRENT]),
        ("", 2005, [EMILY_ROSE_TORRENT]),
    ],
)
def test_other_movies_do_not_match(title, year, names):
    assert not matches_movie(title, year, names)
