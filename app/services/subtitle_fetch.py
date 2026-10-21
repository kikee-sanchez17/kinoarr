import logging
import threading
from pathlib import Path

from app.clients.opensubtitles import OpenSubtitlesClient
from app.models import SubtitleCandidate, SubtitleFetchResult
from app.movie_hash import movie_hash
from app.services.subtitle_detection import SubtitleDetectionService
from app.subtitles import best_candidate, english_sidecar_path, looks_english, matches_movie, read_subtitle_text

logger = logging.getLogger(__name__)

PARTIAL_FILE_SUFFIX = ".part"


class SubtitleNotFoundError(Exception):
    """OpenSubtitles has no usable English subtitle for this movie."""


class SubtitleDownloadsDisabledError(Exception):
    """No OpenSubtitles API key is configured."""


class SubtitleWriteError(Exception):
    """The subtitle could not be saved next to the movie."""


class SubtitleFetchService:
    """Kinoarr's subtitle rules: skip movies that already have one, prefer the torrent's own English subtitle,
    otherwise download the best OpenSubtitles match for the same movie, and save it beside the movie."""

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
        with self._lock:
            report = self._detection_service.detect(torrent_hash)
            if report.has_english_subtitle:
                return SubtitleFetchResult(torrent_hash=torrent_hash, status="already_present", subtitle_file=None)

            video_path = Path(report.video_path)
            copied_path = self._copy_bundled_english_subtitle(torrent_hash, video_path)
            if copied_path:
                logger.info("Copied the subtitle included in torrent %r as %s", report.torrent_name, copied_path.name)
                return SubtitleFetchResult(
                    torrent_hash=torrent_hash, status="copied_from_torrent", subtitle_file=copied_path.name
                )

            if self._opensubtitles_client is None:
                raise SubtitleDownloadsDisabledError("Subtitle downloads are not configured: set OPENSUBTITLES_API_KEY")
            candidate = self._find_candidate(self._opensubtitles_client, video_path, report.torrent_name)
            subtitle_path = english_sidecar_path(video_path)
            _write_atomically(subtitle_path, self._opensubtitles_client.download(candidate.file_id))

        logger.info("Saved subtitle %s for torrent %r", subtitle_path.name, report.torrent_name)
        return SubtitleFetchResult(torrent_hash=torrent_hash, status="downloaded", subtitle_file=subtitle_path.name)

    def _copy_bundled_english_subtitle(self, torrent_hash: str, video_path: Path) -> Path | None:
        for subtitle_path in self._detection_service.bundled_subtitles(torrent_hash):
            try:
                if not looks_english(read_subtitle_text(subtitle_path)):
                    continue
                content = subtitle_path.read_bytes()
            except OSError as exc:
                logger.warning("Cannot read %s, skipping it: %s", subtitle_path.name, exc)
                continue
            # A copy, not a rename: qBittorrent keeps seeding the torrent's own files.
            target_path = english_sidecar_path(video_path, subtitle_path.suffix.lower())
            _write_atomically(target_path, content)
            return target_path
        return None

    def _find_candidate(
        self, opensubtitles: OpenSubtitlesClient, video_path: Path, torrent_name: str
    ) -> SubtitleCandidate:
        download_names = [torrent_name, video_path.stem]
        file_hash = _movie_hash_or_none(video_path)
        candidates = opensubtitles.search_english(movie_hash=file_hash) if file_hash else []
        candidates = _for_same_movie(candidates, download_names)
        if not candidates:
            candidates = _for_same_movie(opensubtitles.search_english(query=torrent_name), download_names)
        candidate = best_candidate(candidates)
        if candidate is None:
            raise SubtitleNotFoundError(f"No English subtitle found on OpenSubtitles for {torrent_name!r}")
        return candidate


def _for_same_movie(candidates: list[SubtitleCandidate], download_names: list[str]) -> list[SubtitleCandidate]:
    # OpenSubtitles users sometimes file a subtitle under the wrong movie, even for exact file-hash matches.
    same_movie = []
    other_movies = set()
    for candidate in candidates:
        if matches_movie(candidate.movie_title, candidate.movie_year, download_names):
            same_movie.append(candidate)
        else:
            other_movies.add(f"{candidate.movie_title} ({candidate.movie_year})")
    if other_movies:
        logger.info(
            "Skipped OpenSubtitles results for other movies than %r: %s",
            download_names[0],
            ", ".join(sorted(other_movies)),
        )
    return same_movie


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
