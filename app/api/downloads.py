from fastapi import APIRouter, Depends, HTTPException

from app.clients.ffprobe import FfprobeError
from app.clients.prowlarr import ProwlarrError
from app.clients.qbittorrent import QBittorrentClient, QBittorrentError, QBittorrentRejectedError
from app.dependencies import get_download_service, get_qbittorrent_client, get_subtitle_detection_service
from app.models import DownloadRequest, DownloadStarted, SubtitleReport, Torrent
from app.services.downloads import DownloadService, ReleaseNotFoundError
from app.services.subtitle_detection import (
    DownloadPathMissingError,
    SubtitleDetectionService,
    TorrentNotFinishedError,
    TorrentNotFoundError,
    VideoNotFoundError,
)

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
    except TorrentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TorrentNotFinishedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (DownloadPathMissingError, FfprobeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except QBittorrentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
