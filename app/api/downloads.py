from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException

from app.clients.ffprobe import FfprobeError
from app.clients.opensubtitles import OpenSubtitlesError, QuotaExceededError
from app.clients.prowlarr import ProwlarrError
from app.clients.qbittorrent import QBittorrentClient, QBittorrentError, QBittorrentRejectedError
from app.dependencies import (
    get_download_service,
    get_qbittorrent_client,
    get_subtitle_detection_service,
    get_subtitle_fetch_service,
)
from app.models import DownloadRequest, DownloadStarted, SubtitleFetchResult, SubtitleReport, Torrent
from app.services.downloads import DownloadService, ReleaseNotFoundError
from app.services.subtitle_detection import (
    DownloadPathMissingError,
    SubtitleDetectionService,
    TorrentNotFinishedError,
    TorrentNotFoundError,
    VideoNotFoundError,
)
from app.services.subtitle_fetch import (
    SubtitleDownloadsDisabledError,
    SubtitleFetchService,
    SubtitleNotFoundError,
    SubtitleWriteError,
)

# Checked in order, so a subclass must come before its parent.
DETECTION_ERROR_STATUSES: list[tuple[type[Exception], int]] = [
    (TorrentNotFoundError, 404),
    (TorrentNotFinishedError, 409),
    (VideoNotFoundError, 422),
    (DownloadPathMissingError, 500),
    (FfprobeError, 500),
    (QBittorrentError, 502),
]
FETCH_ERROR_STATUSES: list[tuple[type[Exception], int]] = [
    (SubtitleNotFoundError, 404),
    (QuotaExceededError, 429),
    (OpenSubtitlesError, 502),
    (SubtitleDownloadsDisabledError, 503),
    (SubtitleWriteError, 500),
    *DETECTION_ERROR_STATUSES,
]

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.get("/status")
def qbittorrent_status(qbittorrent: QBittorrentClient = Depends(get_qbittorrent_client)) -> dict:
    """Check the connection and login to qBittorrent."""
    try:
        return {"connected": True, "qbittorrent_version": qbittorrent.version()}
    except QBittorrentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[Torrent])
def list_downloads(
    completed: bool = False,
    qbittorrent: QBittorrentClient = Depends(get_qbittorrent_client),
) -> list[Torrent]:
    """List qBittorrent torrents (only completed ones with ?completed=true)."""
    try:
        return qbittorrent.list_torrents(completed_only=completed)
    except QBittorrentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("", status_code=202, response_model=DownloadStarted)
def start_download(
    request: DownloadRequest,
    download_service: DownloadService = Depends(get_download_service),
) -> DownloadStarted:
    """Send a release from a recent search to qBittorrent."""
    try:
        return download_service.start_download(request.release_id)
    except ReleaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # The rejected error is a QBittorrentError subclass, so it must be caught first.
    except QBittorrentRejectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ProwlarrError, QBittorrentError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{torrent_hash}/subtitles", response_model=SubtitleReport)
def detect_subtitles(
    torrent_hash: str,
    detection_service: SubtitleDetectionService = Depends(get_subtitle_detection_service),
) -> SubtitleReport:
    """Report whether a finished download already has an English subtitle."""
    try:
        return detection_service.detect(torrent_hash)
    except Exception as exc:
        _raise_http_error(exc, DETECTION_ERROR_STATUSES)


@router.post("/{torrent_hash}/subtitles", response_model=SubtitleFetchResult)
def fetch_subtitle(
    torrent_hash: str,
    fetch_service: SubtitleFetchService = Depends(get_subtitle_fetch_service),
) -> SubtitleFetchResult:
    """Download an English subtitle for a finished download, unless it already has one."""
    try:
        return fetch_service.fetch(torrent_hash)
    except Exception as exc:
        _raise_http_error(exc, FETCH_ERROR_STATUSES)


def _raise_http_error(exc: Exception, error_statuses: list[tuple[type[Exception], int]]) -> NoReturn:
    """Turn a known error into its HTTP status; re-raise anything unexpected unchanged."""
    for error_type, status_code in error_statuses:
        if isinstance(exc, error_type):
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    raise exc
