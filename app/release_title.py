"""Best-guess video details from a release title.

Prowlarr and OpenSubtitles do not report resolution, codec or source as data, but
release names usually spell them out (e.g. "Movie.1968.1080p.BluRay.x264-GROUP").
"""

import re
from typing import Literal

Resolution = Literal["2160p", "1080p", "720p", "SD"]
VideoCodec = Literal["H.265", "H.264", "AV1", "XviD/DivX"]
# "pre-release" covers cam, telesync, telecine and screener copies, cut and timed differently from the final movie.
ReleaseSource = Literal["pre-release", "BluRay", "WEB", "DVD", "HDTV"]


def _token(pattern: str) -> re.Pattern[str]:
    # Release names separate tokens with dots, spaces, dashes, underscores or brackets.
    # \b would treat "_" as part of a word, so a boundary here is "not a letter or digit".
    return re.compile(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])", re.IGNORECASE)


# Checked in order; the first match wins.
RESOLUTION_PATTERNS: list[tuple[Resolution, re.Pattern[str]]] = [
    ("2160p", _token(r"2160p|4k|uhd")),
    ("1080p", _token(r"1080[pi]")),
    ("720p", _token(r"720p")),
    ("SD", _token(r"576p|480p")),
]
# H.265 comes first: some titles mention both (e.g. "x264 to x265 re-encode").
VIDEO_CODEC_PATTERNS: list[tuple[VideoCodec, re.Pattern[str]]] = [
    ("H.265", _token(r"x\.?265|h\.?265|hevc")),
    ("H.264", _token(r"x\.?264|h\.?264|avc")),
    ("AV1", _token(r"av1")),
    ("XviD/DivX", _token(r"xvid|divx")),
]
# Pre-release first: such a copy is timed differently even if the name mentions another source too.
RELEASE_SOURCE_PATTERNS: list[tuple[ReleaseSource, re.Pattern[str]]] = [
    ("pre-release", _token(r"cam|hdcam|camrip|ts|hdts|telesync|tc|hdtc|telecine|dvdscr|scr|screener|r5")),
    ("BluRay", _token(r"blu-?ray|bdrip|brrip|bd|remux")),
    ("WEB", _token(r"web(?:-?(?:dl|rip))?")),
    ("DVD", _token(r"dvd(?:-?rip)?")),
    ("HDTV", _token(r"hdtv|pdtv")),
]
# YTS (also published as YIFY, on domains like yts.mx) rarely puts its name after a dash.
YTS_GROUP = "yts"
YTS_PATTERN = _token(r"yts|yify")
# The group closes the name: "...x264-GROUP" or "...x264-[GROUP]". "WEB-DL" is a source, not a group.
TRAILING_GROUP_PATTERN = re.compile(r"(?<!web)-\s*\[?([a-z0-9]+)\]?\s*$", re.IGNORECASE)


def detect_resolution(title: str) -> Resolution | None:
    return _first_match(title, RESOLUTION_PATTERNS)


def detect_video_codec(title: str) -> VideoCodec | None:
    return _first_match(title, VIDEO_CODEC_PATTERNS)


def detect_release_source(title: str) -> ReleaseSource | None:
    return _first_match(title, RELEASE_SOURCE_PATTERNS)


def detect_release_group(title: str) -> str | None:
    if YTS_PATTERN.search(title):
        return YTS_GROUP
    match = TRAILING_GROUP_PATTERN.search(title)
    return match.group(1).casefold() if match else None


def _first_match[T](title: str, patterns: list[tuple[T, re.Pattern[str]]]) -> T | None:
    for value, pattern in patterns:
        if pattern.search(title):
            return value
    return None
