import logging
import tempfile
import threading
from pathlib import Path

from app.clients.alass import AlassClient, AlassError
from app.clients.ffprobe import FfprobeClient, FfprobeError
from app.clients.opensubtitles import OpenSubtitlesClient
from app.models import DownloadDetails, SubtitleCandidate, SubtitleFetchResult
from app.movie_hash import movie_hash
from app.services.subtitle_detection import SubtitleDetectionService
from app.subtitles import (
    DEFAULT_SUBTITLE_EXTENSION,
    best_candidate,
    english_sidecar_path,
    looks_english,
    matches_movie,
    read_subtitle_text,
)

logger = logging.getLogger(__name__)

PARTIAL_FILE_SUFFIX = ".part"
# alass picks the subtitle format from the file extension, so the work files keep ".srt".
UNSYNCED_FILE_NAME = f"unsynced{DEFAULT_SUBTITLE_EXTENSION}"
SYNCED_FILE_NAME = f"synced{DEFAULT_SUBTITLE_EXTENSION}"
WORK_FOLDER_PREFIX = "kinoarr-alass-"


class SubtitleNotFoundError(Exception):
    """OpenSubtitles has no usable English subtitle for this movie."""


class SubtitleDownloadsDisabledError(Exception):
    """No OpenSubtitles API key is configured."""


class SubtitleWriteError(Exception):
    """The subtitle could not be saved next to the movie."""


class SubtitleFetchService:
    """Kinoarr's subtitle rules: skip movies that already have one, prefer the torrent's own English subtitle,
    otherwise download the best OpenSubtitles match for the same movie, re-time it to the movie's audio unless
    it was made for this exact file, and save it beside the movie."""

    def __init__(
        self,
        detection_service: SubtitleDetectionService,
        opensubtitles_client: OpenSubtitlesClient | None,
        ffprobe_client: FfprobeClient,
        alass_client: AlassClient,
    ) -> None:
        self._detection_service = detection_service
        self._opensubtitles_client = opensubtitles_client
        self._ffprobe_client = ffprobe_client
        self._alass_client = alass_client
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
            return self._download_from_opensubtitles(
                self._opensubtitles_client, torrent_hash, video_path, report.torrent_name
            )

    def _download_from_opensubtitles(
        self, opensubtitles: OpenSubtitlesClient, torrent_hash: str, video_path: Path, torrent_name: str
    ) -> SubtitleFetchResult:
        download = self._download_details(video_path, torrent_name)
        candidate = self._find_candidate(opensubtitles, video_path, download)
        subtitle = opensubtitles.download(candidate.file_id)
        synced_to_audio = False
        if not candidate.hash_match:
            subtitle, synced_to_audio = self._synced_or_original(subtitle, video_path)
        subtitle_path = english_sidecar_path(video_path)
        _write_atomically(subtitle_path, subtitle)

        logger.info(
            "Saved subtitle %s for torrent %r (%s)",
            subtitle_path.name,
            torrent_name,
            _describe_choice(candidate, download, synced_to_audio),
        )
        return SubtitleFetchResult(
            torrent_hash=torrent_hash,
            status="downloaded",
            subtitle_file=subtitle_path.name,
            synced_to_audio=synced_to_audio,
        )

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

    def _download_details(self, video_path: Path, torrent_name: str) -> DownloadDetails:
        try:
            frame_rate = self._ffprobe_client.video_frame_rate(video_path)
        except FfprobeError as exc:
            # Ranking still works without it, so this is not fatal.
            logger.warning(
                "Cannot read the frame rate of %s, choosing the subtitle without it: %s", video_path.name, exc
            )
            frame_rate = None
        return DownloadDetails(names=[torrent_name, video_path.stem], frame_rate=frame_rate)

    def _find_candidate(
        self, opensubtitles: OpenSubtitlesClient, video_path: Path, download: DownloadDetails
    ) -> SubtitleCandidate:
        torrent_name = download.names[0]
        file_hash = _movie_hash_or_none(video_path)
        candidates = opensubtitles.search_english(movie_hash=file_hash) if file_hash else []
        candidates = _for_same_movie(candidates, download.names)
        if not candidates:
            candidates = _for_same_movie(opensubtitles.search_english(query=torrent_name), download.names)
        candidate = best_candidate(candidates, download)
        if candidate is None:
            raise SubtitleNotFoundError(f"No English subtitle found on OpenSubtitles for {torrent_name!r}")
        return candidate

    def _synced_or_original(self, subtitle: bytes, video_path: Path) -> tuple[bytes, bool]:
        """The subtitle re-timed to the movie's audio, or the original if alass cannot do it."""
        try:
            return self._synced(subtitle, video_path), True
        except AlassError as exc:
            # A subtitle that may be off is still better than none.
            logger.warning("Saving the subtitle for %s without re-timing it: %s", video_path.name, exc)
            return subtitle, False

    def _synced(self, subtitle: bytes, video_path: Path) -> bytes:
        # The work files live outside the media folder, so Jellyfin never sees them.
        try:
            with tempfile.TemporaryDirectory(prefix=WORK_FOLDER_PREFIX) as work_folder:
                unsynced_path = Path(work_folder) / UNSYNCED_FILE_NAME
                synced_path = Path(work_folder) / SYNCED_FILE_NAME
                unsynced_path.write_bytes(subtitle)
                self._alass_client.sync(video_path, unsynced_path, synced_path)
                return _read_alass_output(synced_path)
        except OSError as exc:
            raise AlassError(f"cannot prepare the files for alass: {exc}") from exc


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


def _describe_choice(candidate: SubtitleCandidate, download: DownloadDetails, synced_to_audio: bool) -> str:
    match = "hash match" if candidate.hash_match else "name match"
    timing = "synced to the audio" if synced_to_audio else "not re-timed"
    return (
        f"{match}, release {candidate.release_name or 'unknown'!r}, {_frame_rate_text(candidate.frame_rate)}, "
        f"video {_frame_rate_text(download.frame_rate)}, {timing}"
    )


def _frame_rate_text(frame_rate: float | None) -> str:
    return f"{frame_rate:.3f} fps" if frame_rate else "unknown fps"


def _read_alass_output(path: Path) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise AlassError(f"alass wrote no subtitle: {exc}") from exc
    if not content:
        raise AlassError("alass wrote an empty subtitle")
    return content


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
