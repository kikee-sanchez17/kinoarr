from functools import lru_cache

from app.clients.qbittorrent import QBittorrentClient
from app.config import get_settings


@lru_cache
def get_qbittorrent_client() -> QBittorrentClient:
    s = get_settings()
    return QBittorrentClient(
        s.qbittorrent_url,
        s.qbittorrent_username,
        s.qbittorrent_password,
        remote_downloads_path=s.qbittorrent_downloads_path,
        local_downloads_path=s.kinoarr_downloads_path,
    )