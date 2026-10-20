from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    """Settings loaded from environment variables or the .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # qBittorrent
    qbittorrent_url: str = "http://qbittorrent:8081"
    qbittorrent_username: str = "admin"
    qbittorrent_password: str = ""

    # Jellyfin
    jellyfin_url: str = "http://host.docker.internal:8096"
    jellyfin_api_key: str = ""

    # Prowlarr (Torznab API)
    prowlarr_url: str = "http://prowlarr:9696"
    prowlarr_api_key: str = ""

    # External APIs
    tmdb_api_key: str = ""
    opensubtitles_api_key: str = ""
    # Optional: logging in raises the daily download quota.
    opensubtitles_username: str = ""
    opensubtitles_password: str = ""

    # Subtitles: comma-separated list (only "en" for now)
    subtitle_languages: str = "en"

    # Path mapping: the downloads folder as qBittorrent sees it and as Kinoarr
    # sees it. Leave either empty to disable mapping.
    qbittorrent_downloads_path: str = ""
    kinoarr_downloads_path: str = ""

    # Poller
    poll_interval: int = 60

    @property
    def subtitle_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.subtitle_languages.split(",") if lang.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
