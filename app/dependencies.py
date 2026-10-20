from functools import lru_cache

from app.clients.ffprobe import FfprobeClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.qbittorrent import QBittorrentClient
from app.config import get_settings
from app.services.downloads import DownloadService
from app.services.release_store import ReleaseStore
from app.services.search import SearchService
from app.services.subtitle_detection import SubtitleDetectionService


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


@lru_cache
def get_prowlarr_client() -> ProwlarrClient:
    settings = get_settings()
    return ProwlarrClient(settings.prowlarr_url, settings.prowlarr_api_key)


@lru_cache
def get_release_store() -> ReleaseStore:
    return ReleaseStore()


@lru_cache
def get_search_service() -> SearchService:
    return SearchService(get_prowlarr_client(), get_release_store())


@lru_cache
def get_download_service() -> DownloadService:
    return DownloadService(get_release_store(), get_prowlarr_client(), get_qbittorrent_client())


@lru_cache
def get_ffprobe_client() -> FfprobeClient:
    return FfprobeClient()


@lru_cache
def get_subtitle_detection_service() -> SubtitleDetectionService:
    return SubtitleDetectionService(get_qbittorrent_client(), get_ffprobe_client())
