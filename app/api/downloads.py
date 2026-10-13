from fastapi import APIRouter, Depends, HTTPException

from app.clients.qbittorrent import QBittorrentClient, QBittorrentError
from app.dependencies import get_qbit_client
from app.models import Torrent

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.get("/status")
def qbit_status(qbit: QBittorrentClient = Depends(get_qbit_client)) -> dict:
    """Comprueba la conexión y el login con qBittorrent."""
    try:
        return {"connected": True, "qbittorrent_version": qbit.version()}
    except QBittorrentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[Torrent])
def list_downloads(
    completed: bool = False,
    qbit: QBittorrentClient = Depends(get_qbit_client),
) -> list[Torrent]:
    """Lista los torrents de qBittorrent (solo los completados con ?completed=true)."""
    try:
        return qbit.list_torrents(completed_only=completed)
    except QBittorrentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc