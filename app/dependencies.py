from functools import lru_cache

from app.clients.qbittorrent import QBittorrentClient
from app.config import get_settings


@lru_cache
def get_qbit_client() -> QBittorrentClient:
    s = get_settings()
    return QBittorrentClient(
        s.qbit_url,
        s.qbit_username,
        s.qbit_password,
        remote_downloads_path=s.qbittorrent_downloads_path,
        local_downloads_path=s.kinoarr_downloads_path,
    )