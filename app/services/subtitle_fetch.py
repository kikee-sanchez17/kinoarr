import logging
import threading
from pathlib import Path

from app.clients.opensubtitles import OpenSubtitlesClient
from app.models import SubtitleCandidate, SubtitleFetchResult
from app.movie_hash import movie_hash
from app.services.subtitle_detection import SubtitleDetectionService
from app.subtitles import best_candidate, english_sidecar_path

logger = logging.getLogger(__name__)

PARTIAL_FILE_SUFFIX = ".part"


class SubtitleNotFoundError(Exception):
    """OpenSubtitles has no usable English subtitle for this movie."""


class SubtitleDownloadsDisabledError(Exception):
    """No OpenSubtitles API key is configured."""


class SubtitleWriteError(Exception):
    """The subtitle could not be saved next to the movie."""


class SubtitleFetchService:
    """Kinoarr's subtitle rules: skip movies that already have one, pick the best match, save it beside the movie."""

    def __init__(
        self,
        detection_service: SubtitleDetectionService,
        opensubtitles_client: OpenSubtitlesClient | None,
    ) -> None:
        self._detection_service = detection_service
        self._opensubtitles_client = opensubtitles_client
        # One download at a time, so the manual endpoint and the checker never fetch the same movie twice.
        self._lock = threading.Lock()

    def fetch(self, torrent_hash: str) -> SubtitleFetchResult:
        if self._opensubtitles_client is None:
            raise SubtitleDownloadsDisabledError("Subtitle downloads are not configured: set OPENSUBTITLES_API_KEY")
        with self._lock:
            report = self._detection_service.detect(torrent_hash)
            if report.has_english_subtitle:
                return SubtitleFetchResult(torrent_hash=torrent_hash, status="already_present", subtitle_file=None)

            video_path = Path(report.video_path)
            candidate = self._find_candidate(self._opensubtitles_client, video_path, report.torrent_name)
            subtitle_path = english_sidecar_path(video_path)
            _write_atomically(subtitle_path, self._opensubtitles_client.download(candidate.file_id))

        logger.info("Saved subtitle %s for torrent %r", subtitle_path.name, report.torrent_name)
        return SubtitleFetchResult(torrent_hash=torrent_hash, status="downloaded", subtitle_file=subtitle_path.name)

    def _find_candidate(
        self, opensubtitles: OpenSubtitlesClient, video_path: Path, torrent_name: str
    ) -> SubtitleCandidate:
        file_hash = _movie_hash_or_none(video_path)
        candidates = opensubtitles.search_english(movie_hash=file_hash) if file_hash else []
        if not candidates:
            candidates = opensubtitles.search_english(query=torrent_name)
        candidate = best_candidate(candidates)
        if candidate is None:
            raise SubtitleNotFoundError(f"No English subtitle found on OpenSubtitles for {torrent_name!r}")
        return candidate


def _movie_hash_or_none(video_path: Path) -> str | None:
    try:
        return movie_hash(video_path)
    except OSError as exc:
        # The name search still works without the hash, so this is not fatal.
        logger.warning("Cannot hash %s, searching by name only: %s", video_path.name, exc)
        return None


def _write_atomically(path: Path, content: bytes) -> None:
    # Write next to the target, then rename: Jellyfin never sees a half-written subtitle.
    partial_path = path.with_name(path.name + PARTIAL_FILE_SUFFIX)
    try:
        partial_path.write_bytes(content)
        partial_path.replace(path)
    except OSError as exc:
        partial_path.unlink(missing_ok=True)
        raise SubtitleWriteError(
            f"Cannot write {path.name}: check that Kinoarr can write to the downloads folder (PUID/PGID)"
        ) from exc
