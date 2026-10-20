from pathlib import Path

from app.clients.ffprobe import FfprobeClient
from app.clients.qbittorrent import QBittorrentClient
from app.models import FoundSubtitle, SubtitleReport, SubtitleStream, Torrent
from app.subtitles import english_sidecars, find_main_video, is_english_embedded

FINISHED_PROGRESS = 1.0


class TorrentNotFoundError(Exception):
    """qBittorrent has no torrent with this hash."""


class TorrentNotFinishedError(Exception):
    """The torrent is still downloading."""


class VideoNotFoundError(Exception):
    """The torrent contains no video file."""


class DownloadPathMissingError(Exception):
    """The torrent's path does not exist as Kinoarr sees it (usually wrong path mapping)."""


class SubtitleDetectionService:
    """Kinoarr's detection rules: which file to check and which subtitles count as English."""

    def __init__(self, qbittorrent_client: QBittorrentClient, ffprobe_client: FfprobeClient) -> None:
        self._qbittorrent_client = qbittorrent_client
        self._ffprobe_client = ffprobe_client

    def detect(self, torrent_hash: str) -> SubtitleReport:
        torrent = self._finished_torrent(torrent_hash)
        video_path = _main_video_of(torrent)
        found = [
            _describe_embedded(stream)
            for stream in self._ffprobe_client.subtitle_streams(video_path)
            if is_english_embedded(stream)
        ]
        found += [FoundSubtitle(source="sidecar", description=path.name) for path in english_sidecars(video_path)]
        return SubtitleReport(
            torrent_hash=torrent_hash,
            torrent_name=torrent.name,
            video_path=str(video_path),
            has_english_subtitle=bool(found),
            english_subtitles=found,
        )

    def _finished_torrent(self, torrent_hash: str) -> Torrent:
        torrent = self._qbittorrent_client.get_torrent(torrent_hash)
        if torrent is None:
            raise TorrentNotFoundError(f"No torrent with hash {torrent_hash}")
        if torrent.progress < FINISHED_PROGRESS:
            raise TorrentNotFinishedError(f"Torrent {torrent.name!r} has not finished downloading")
        return torrent


def _main_video_of(torrent: Torrent) -> Path:
    content_path = Path(torrent.content_path)
    if not content_path.exists():
        raise DownloadPathMissingError(
            f"{content_path} does not exist for Kinoarr: "
            "check QBITTORRENT_DOWNLOADS_PATH and KINOARR_DOWNLOADS_PATH"
        )

    video_path = find_main_video(content_path)
    if video_path is None:
        raise VideoNotFoundError(f"Torrent {torrent.name!r} contains no video file")
    return video_path


def _describe_embedded(stream: SubtitleStream) -> FoundSubtitle:
    return FoundSubtitle(source="embedded", description=f"track {stream.index} ({stream.codec}, {stream.language})")
