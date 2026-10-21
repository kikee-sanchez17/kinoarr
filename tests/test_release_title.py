import pytest

from app.release_title import detect_resolution, detect_video_codec


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Night.of.the.Living.Dead.1968.REMASTERED.1080p.BluRay.X264-AMIAB", "1080p"),
        ("Night of the Living Dead (1968) 2160p BRRip 5.1 10Bit x265 -YTS", "2160p"),
        ("Night of the Living Dead (1968) 720p BRRip x264 -YTS", "720p"),
        ("Movie 1999 4K HDR", "2160p"),
        ("Movie.1999.UHD.BluRay", "2160p"),
        ("Movie 1999 1080i HDTV", "1080p"),
        ("Movie.1999.DVDRip.576p", "SD"),
        ("Movie_1999_480p_XviD", "SD"),
        ("Movie [1080p] [YTS]", "1080p"),
        ("movie.1999.1080P.web", "1080p"),
        ("Night of the Living Dead 1968 Criterion RM4k 1080p BluRay", "1080p"),
        ("Night of the Living Dead (1968)", None),
        ("Movie 1720p", None),
        ("Movie for 4kids", None),
    ],
)
def test_detect_resolution(title: str, expected: str | None):
    assert detect_resolution(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Night.of.the.Living.Dead.1968.REMASTERED.1080p.BluRay.X264-AMIAB", "H.264"),
        ("Night Of The Living Dead 1990 REMASTERED UNRATED 1080p BluRay HEVC x265 5.1 BONE", "H.265"),
        ("Movie.1999.1080p.WEB-DL.H.264", "H.264"),
        ("Movie 1999 1080p H265", "H.265"),
        ("Movie.1999.x.265", "H.265"),
        ("Movie 1999 AVC Remux", "H.264"),
        ("Movie.1999.1080p.AV1.Opus", "AV1"),
        ("Movie_1999_DVDRip_XviD-GROUP", "XviD/DivX"),
        ("Movie 1999 DivX", "XviD/DivX"),
        ("Movie 1999 x264 to x265 re-encode", "H.265"),
        ("Night of the Living Dead (1968)", None),
        ("The AV Club Movie avclub", None),
        ("Movie 1999 x2640", None),
    ],
)
def test_detect_video_codec(title: str, expected: str | None):
    assert detect_video_codec(title) == expected
