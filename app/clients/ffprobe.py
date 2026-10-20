import json
import subprocess
from pathlib import Path
from typing import Any

from app.models import SubtitleStream

DEFAULT_EXECUTABLE = "ffprobe"
# ffprobe only reads the file headers, but files on network storage can be slow.
FFPROBE_TIMEOUT_SECONDS = 60
SUBTITLE_STREAM_ENTRIES = (
    "stream=index,codec_name:stream_tags=language,title:stream_disposition=forced,hearing_impaired"
)


class FfprobeError(Exception):
    """ffprobe is missing, failed, or returned something unexpected."""


class FfprobeClient:
    """Runs ffprobe as a subprocess: translates calls, holds no Kinoarr logic."""

    def __init__(self, executable: str = DEFAULT_EXECUTABLE) -> None:
        self._executable = executable

    def subtitle_streams(self, video_path: Path) -> list[SubtitleStream]:
        output = self._run(video_path)
        try:
            raw_streams = json.loads(output).get("streams", [])
            return [_to_subtitle_stream(raw) for raw in raw_streams]
        except (ValueError, AttributeError, KeyError, TypeError) as exc:
            raise FfprobeError(f"Unexpected ffprobe output for {video_path.name}") from exc

    def _run(self, video_path: Path) -> str:
        # Arguments as a list (no shell), so file names with spaces or quotes are safe.
        command = [
            self._executable,
            "-v", "error",
            "-select_streams", "s",
            "-print_format", "json",
            "-show_entries", SUBTITLE_STREAM_ENTRIES,
            str(video_path),
        ]  # fmt: skip
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_SECONDS, check=False
            )
        except FileNotFoundError as exc:
            raise FfprobeError(f"{self._executable} not found: install ffmpeg") from exc
        except subprocess.TimeoutExpired as exc:
            raise FfprobeError(f"ffprobe timed out on {video_path.name}") from exc
        if result.returncode != 0:
            reason = result.stderr.strip().splitlines()[0] if result.stderr.strip() else f"exit code {result.returncode}"
            raise FfprobeError(f"ffprobe could not read {video_path.name}: {reason}")
        return result.stdout


def _to_subtitle_stream(raw: dict[str, Any]) -> SubtitleStream:
    tags = raw.get("tags", {})
    disposition = raw.get("disposition", {})
    return SubtitleStream(
        index=raw["index"],
        codec=raw.get("codec_name"),
        language=tags.get("language"),
        title=tags.get("title"),
        forced=bool(disposition.get("forced", 0)),
        hearing_impaired=bool(disposition.get("hearing_impaired", 0)),
    )
