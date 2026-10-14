from fastapi import APIRouter, Depends, HTTPException

from app.clients.qbittorrent import QBittorrentClient, QBittorrentError
from app.dependencies import get_qbittorrent_client
from app.models import Torrent

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