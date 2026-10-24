import pytest

from app.release_title import detect_release_group, detect_release_source, detect_resolution, detect_video_codec


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


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # Release names from a real OpenSubtitles search for Lady Bird (2017)
        ("Lady Bird 2017 DVDScr XVID AC3 HQ Hive-CM8", "pre-release"),
        ("Lady.Bird.2017.720p.BluRay.x264.DTS-HDC", "BluRay"),
        ("Lady.Bird.2017.720p.WEB-DL.DD5.1.H264-FGT", "WEB"),
        ("Lady Bird (2017) [BluRay] [1080p] [YTS.AM]", "BluRay"),
        ("The.Exorcism.of.Emily.Rose.UNRATED.2005.1080p.BrRip.x264.BOKUTOX.YIFY", "BluRay"),
        ("Movie.1999.BDRip.x264", "BluRay"),
        ("Movie 1999 1080p Remux", "BluRay"),
        ("Movie.1999.1080p.WEBRip.x264", "WEB"),
        ("Movie.1999.1080p.WEB.h264", "WEB"),
        ("Movie_1999_DVDRip_XviD-GROUP", "DVD"),
        ("Movie.1999.HDTV.x264", "HDTV"),
        ("Movie 1999 HDCAM", "pre-release"),
        ("Movie.1999.HDTS.x264", "pre-release"),
        ("Movie.1999.TS.XviD", "pre-release"),
        ("Movie.1999.Telesync", "pre-release"),
        ("Movie 1999 R5 LiNE", "pre-release"),
        ("Lady Bird (2017)", None),
        ("Movie.1999.1080p.x264.DTS", None),
        ("Movie.1999.BD25", None),
    ],
)
def test_detect_release_source(title: str, expected: str | None):
    assert detect_release_source(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Lady.Bird.2017.720p.BluRay.x264.DTS-HDC", "hdc"),
        ("Lady.Bird.2017.720p.WEB-DL.DD5.1.H264-FGT", "fgt"),
        ("Lady Bird 2017 DVDScr XVID AC3 HQ Hive-CM8", "cm8"),
        ("Lady Bird (2017) [BluRay] [1080p] [YTS.AM]", "yts"),
        ("Lady.Bird.2017.1080p.BluRay.x264-[YTS.AM]", "yts"),
        ("The.Exorcism.of.Emily.Rose.UNRATED.2005.1080p.BrRip.x264.BOKUTOX.YIFY", "yts"),
        ("Night of the Living Dead (1968) 720p BRRip x264 -YTS", "yts"),
        ("Movie.1999.1080p.BluRay.x264-[RARBG]", "rarbg"),
        ("Movie.1999.1080p.WEB-DL", None),
        ("Lady Bird (2017)", None),
        ("Dave.Chappelle.The.Bird.Revelation.2017.1080p.Netflix.WEB-DL.DD5.1.x264-QOQ__english", None),
    ],
)
def test_detect_release_group(title: str, expected: str | None):
    assert detect_release_group(title) == expected
