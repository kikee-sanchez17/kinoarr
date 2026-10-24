"""Rules for finding a download's movie file and deciding which subtitles count as English.

Kept as small pure functions (the only I/O is listing folders and reading subtitle files) because the
matching rules are where the edge cases live.
"""

import codecs
import html
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from app.models import DownloadDetails, SubtitleCandidate, SubtitleStream
from app.release_title import ReleaseSource, detect_release_group, detect_release_source

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".webm", ".ogv"}
# The text formats Jellyfin reads as external subtitles.
SIDECAR_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}
ENGLISH_TAGS = {"en", "eng"}
FORCED_TAGS = {"forced"}
SDH_TAGS = {"sdh", "hi", "cc"}
# Many releases mark SDH tracks only in the title, not in the disposition flag.
SDH_TITLE_MARKER = "sdh"
TAG_SEPARATOR = "."
# Recognised by `is_english_sidecar` and by Jellyfin.
ENGLISH_SIDECAR_TAG = ".en"
DEFAULT_SUBTITLE_EXTENSION = ".srt"

# File names inside torrents mark the language in many ways: "Movie.en.srt", "Subs/2_English.srt".
ENGLISH_NAME_TAGS = {"en", "eng", "english"}
NAME_TOKEN_PATTERN = re.compile(r"[^a-z0-9]+")

# Frequent English words that Spanish, French, Italian and German dialogue almost never contains.
# Words shared with them ("a", "no", "me", "in", "son", German "was"/"will", Italian "come") are left out on purpose.
COMMON_ENGLISH_WORDS = frozenset(
    """
    the and you what that this with have are your for not just know don't it's i'm
    can't there they we're you're all but get got how why who when where would could should
    been about from out here right yeah okay well want think going look tell said
    she him his them our they're let's did does doesn't didn't won't of to is it be my
    """.split()
)
# English dialogue scores about 0.4-0.55 on this share; Spanish, French, Italian and German stay under 0.05.
ENGLISH_WORD_SHARE = 0.25
MIN_WORDS_TO_JUDGE = 100
SUBTITLE_TIMING_PATTERN = re.compile(r"^\s*\d+\s*$|-->", re.MULTILINE)
SUBTITLE_MARKUP_PATTERN = re.compile(r"<[^>]*>|\{[^}]*\}")
WORD_PATTERN = re.compile(r"[a-z]+(?:'[a-z]+)?")
# Old subtitle files are often in the Windows Western encoding; it decodes any byte, so it comes last.
FALLBACK_SUBTITLE_ENCODING = "cp1252"

LEADING_ARTICLES = {"the", "a", "an"}
YEAR_PATTERN = re.compile(r"^(19|20)\d\d$")

PRE_RELEASE: ReleaseSource = "pre-release"
# Release frame rates are written rounded (23.976 for 24000/1001), so equal means "this close".
FRAME_RATE_TOLERANCE = 0.01
FRAME_RATE_MATCH = 2
FRAME_RATE_UNKNOWN = 1
FRAME_RATE_MISMATCH = 0


def find_main_video(content_path: Path) -> Path | None:
    """Return the movie file: the path itself if it is a video, else the largest video under it."""
    if content_path.is_file():
        return content_path if _is_video(content_path) else None
    videos = [path for path in content_path.rglob("*") if path.is_file() and _is_video(path)]
    return max(videos, key=lambda path: path.stat().st_size, default=None)


def is_english_embedded(stream: SubtitleStream) -> bool:
    if stream.forced or stream.hearing_impaired:
        return False
    if stream.title and SDH_TITLE_MARKER in stream.title.casefold():
        return False
    return (stream.language or "").casefold() in ENGLISH_TAGS


def is_english_sidecar(subtitle_name: str, video_stem: str) -> bool:
    """`Movie.en.srt` is an English sidecar of video `Movie`; `Movie.en.forced.srt` or `Movie.srt` are not."""
    subtitle_path = Path(subtitle_name)
    if subtitle_path.suffix.casefold() not in SIDECAR_EXTENSIONS:
        return False
    prefix = video_stem + TAG_SEPARATOR
    if not subtitle_path.stem.startswith(prefix):
        return False
    tags = {tag.casefold() for tag in subtitle_path.stem[len(prefix) :].split(TAG_SEPARATOR)}
    return bool(tags & ENGLISH_TAGS) and not tags & (FORCED_TAGS | SDH_TAGS)


def english_sidecars(video_path: Path) -> list[Path]:
    # Only the video's own folder: Jellyfin does not read subtitles from subfolders.
    return sorted(
        path
        for path in video_path.parent.iterdir()
        if path.is_file() and is_english_sidecar(path.name, video_path.stem)
    )


def english_sidecar_path(video_path: Path, extension: str = DEFAULT_SUBTITLE_EXTENSION) -> Path:
    return video_path.with_name(video_path.stem + ENGLISH_SIDECAR_TAG + extension)


def bundled_subtitles(content_path: Path) -> list[Path]:
    """Subtitle files shipped inside a torrent's folder, most likely English first.

    A single-file torrent has no folder of its own: its parent holds other downloads, so nothing is returned.
    """
    if content_path.is_file():
        return []
    subtitles = [
        path
        for path in content_path.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in SIDECAR_EXTENSIONS
        and not _name_tokens(path) & (FORCED_TAGS | SDH_TAGS)
    ]
    # A full subtitle is larger than a forced or partial one.
    return sorted(subtitles, key=lambda path: (not _name_tokens(path) & ENGLISH_NAME_TAGS, -path.stat().st_size))


def read_subtitle_text(path: Path) -> str:
    content = path.read_bytes()
    if content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return content.decode("utf-16")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode(FALLBACK_SUBTITLE_ENCODING, errors="replace")


def looks_english(subtitle_text: str) -> bool:
    """Whether the dialogue in a subtitle file is English, judged by how often common English words appear."""
    dialogue = SUBTITLE_MARKUP_PATTERN.sub(" ", subtitle_text)
    dialogue_lines = [line for line in dialogue.splitlines() if not SUBTITLE_TIMING_PATTERN.search(line)]
    words = WORD_PATTERN.findall(" ".join(dialogue_lines).casefold().replace("’", "'"))
    if len(words) < MIN_WORDS_TO_JUDGE:
        return False
    english_words = sum(word in COMMON_ENGLISH_WORDS for word in words)
    return english_words / len(words) >= ENGLISH_WORD_SHARE


def normalize_title(text: str) -> list[str]:
    """Lowercase words without accents or punctuation: "The.Exorcism.of" and "the exorcism of" become equal."""
    # OpenSubtitles returns some titles HTML-escaped ("Wallace &amp; Gromit").
    without_accents = unicodedata.normalize("NFKD", html.unescape(text)).encode("ascii", "ignore").decode()
    return [word for word in NAME_TOKEN_PATTERN.split(without_accents.casefold().replace("&", " and ")) if word]


def matches_movie(title: str | None, year: int | None, names: list[str]) -> bool:
    """Whether a subtitle's movie (title and year) is the one in any of the download's names."""
    title_words = normalize_title(title or "")
    if not title_words:
        return False
    if len(title_words) > 1 and title_words[0] in LEADING_ARTICLES:
        title_words = title_words[1:]
    return any(_contains_run(normalize_title(name), title_words) and _year_fits(name, year) for name in names)


def best_candidate(candidates: list[SubtitleCandidate], download: DownloadDetails) -> SubtitleCandidate | None:
    """Prefer subtitles timed for this release: the exact file, then a final cut, the same frame rate,
    source and group, then the most downloaded."""
    download_source = _first_detected(detect_release_source, download.names)
    download_group = _first_detected(detect_release_group, download.names)

    def ranking(candidate: SubtitleCandidate) -> tuple[bool, bool, int, bool, bool, int]:
        release_name = candidate.release_name or ""
        source = detect_release_source(release_name)
        return (
            candidate.hash_match,
            # A pre-release subtitle only fits a pre-release download.
            source != PRE_RELEASE or download_source == PRE_RELEASE,
            frame_rate_fit(candidate.frame_rate, download.frame_rate),
            download_source is not None and source == download_source,
            download_group is not None and detect_release_group(release_name) == download_group,
            candidate.download_count,
        )

    return max(candidates, key=ranking, default=None)


def frame_rate_fit(subtitle_frame_rate: float | None, video_frame_rate: float | None) -> int:
    if subtitle_frame_rate is None or video_frame_rate is None:
        return FRAME_RATE_UNKNOWN
    if abs(subtitle_frame_rate - video_frame_rate) <= FRAME_RATE_TOLERANCE:
        return FRAME_RATE_MATCH
    return FRAME_RATE_MISMATCH


def _first_detected[T](detect: Callable[[str], T | None], names: list[str]) -> T | None:
    return next((value for name in names if (value := detect(name)) is not None), None)


def _name_tokens(path: Path) -> set[str]:
    return {token for token in NAME_TOKEN_PATTERN.split(path.stem.casefold()) if token}


def _contains_run(words: list[str], run: list[str]) -> bool:
    return any(words[start : start + len(run)] == run for start in range(len(words) - len(run) + 1))


def _year_fits(name: str, year: int | None) -> bool:
    name_years = {int(word) for word in normalize_title(name) if YEAR_PATTERN.match(word)}
    return year is None or not name_years or year in name_years


def _is_video(path: Path) -> bool:
    return path.suffix.casefold() in VIDEO_EXTENSIONS
