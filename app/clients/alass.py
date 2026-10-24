import subprocess
from pathlib import Path

DEFAULT_EXECUTABLE = "alass"
# alass reads the whole audio track through ffmpeg; a long movie on a slow server takes a few minutes.
ALASS_TIMEOUT_SECONDS = 600
ERROR_PREFIX = "error:"


class AlassError(Exception):
    """alass is missing, failed, or took too long."""


class AlassClient:
    """Runs alass as a subprocess: translates calls, holds no Kinoarr logic."""

    def __init__(self, executable: str = DEFAULT_EXECUTABLE) -> None:
        self._executable = executable

    def sync(self, video_path: Path, subtitle_path: Path, output_path: Path) -> None:
        """Write to output_path a copy of the subtitle re-timed to the video's audio."""
        # Arguments as a list (no shell), so file names with spaces or quotes are safe.
        command = [self._executable, str(video_path), str(subtitle_path), str(output_path)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=ALASS_TIMEOUT_SECONDS, check=False)
        except FileNotFoundError as exc:
            raise AlassError(f"{self._executable} not found: install alass to re-time subtitles") from exc
        except subprocess.TimeoutExpired as exc:
            raise AlassError(f"alass timed out on {video_path.name}") from exc
        if result.returncode != 0:
            reason = _error_line(result.stdout + result.stderr) or f"exit code {result.returncode}"
            raise AlassError(f"alass could not re-time the subtitle for {video_path.name}: {reason}")


def _error_line(output: str) -> str | None:
    # alass prints its errors on stdout, after any progress lines, as "error: ...".
    return next((line.strip() for line in output.splitlines() if line.startswith(ERROR_PREFIX)), None)
