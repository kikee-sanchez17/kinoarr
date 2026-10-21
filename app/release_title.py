"""Best-guess video details from a release title.

Prowlarr does not report resolution or codec as data, but release names usually
spell them out (e.g. "Movie.1968.1080p.BluRay.x264-GROUP").
"""

import re
from typing import Literal

Resolution = Literal["2160p", "1080p", "720p", "SD"]
VideoCodec = Literal["H.265", "H.264", "AV1", "XviD/DivX"]


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


def detect_resolution(title: str) -> Resolution | None:
    return _first_match(title, RESOLUTION_PATTERNS)


def detect_video_codec(title: str) -> VideoCodec | None:
    return _first_match(title, VIDEO_CODEC_PATTERNS)


def _first_match[T](title: str, patterns: list[tuple[T, re.Pattern[str]]]) -> T | None:
    for value, pattern in patterns:
        if pattern.search(title):
            return value
    return None
