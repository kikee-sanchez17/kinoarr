"""Rules for finding a download's movie file and deciding which subtitles count as English.

Kept as small pure functions (the only I/O is listing folders) because the
matching rules are where the edge cases live.
"""

from pathlib import Path

from app.models import SubtitleStream

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".webm", ".ogv"}
# The text formats Jellyfin reads as external subtitles.
SIDECAR_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}
ENGLISH_TAGS = {"en", "eng"}
FORCED_TAGS = {"forced"}
SDH_TAGS = {"sdh", "hi", "cc"}
# Many releases mark SDH tracks only in the title, not in the disposition flag.
SDH_TITLE_MARKER = "sdh"
TAG_SEPARATOR = "."


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


def _is_video(path: Path) -> bool:
    return path.suffix.casefold() in VIDEO_EXTENSIONS
