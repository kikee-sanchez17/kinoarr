from functools import lru_cache

from app.clients.ffprobe import FfprobeClient
from app.clients.opensubtitles import OpenSubtitlesClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.qbittorrent import QBittorrentClient
from app.config import APP_VERSION, get_settings
from app.services.downloads import DownloadService
from app.services.release_store import ReleaseStore
from app.services.search import SearchService
from app.services.subtitle_checker import SubtitleChecker
from app.services.subtitle_detection import SubtitleDetectionService
from app.services.subtitle_fetch import SubtitleFetchService


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


@lru_cache
def get_opensubtitles_client() -> OpenSubtitlesClient | None:
    """None when no API key is configured: subtitle downloads are then disabled."""
    settings = get_settings()
    if not settings.opensubtitles_api_key:
        return None
    return OpenSubtitlesClient(
        settings.opensubtitles_api_key,
        settings.opensubtitles_username,
        settings.opensubtitles_password,
        user_agent=f"Kinoarr v{APP_VERSION}",
    )


@lru_cache
def get_subtitle_fetch_service() -> SubtitleFetchService:
    return SubtitleFetchService(get_subtitle_detection_service(), get_opensubtitles_client())


@lru_cache
def get_subtitle_checker() -> SubtitleChecker:
    return SubtitleChecker(get_qbittorrent_client(), get_subtitle_fetch_service())
