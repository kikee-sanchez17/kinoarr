from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno / fichero .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # qBittorrent
    qbit_url: str = "http://qbittorrent:8081"
    qbit_username: str = "admin"
    qbit_password: str = ""

    # Jellyfin
    jellyfin_url: str = "http://host.docker.internal:8096"
    jellyfin_api_key: str = ""

    # Prowlarr (API Torznab)
    prowlarr_url: str = "http://prowlarr:9696"
    prowlarr_api_key: str = ""

    # APIs externas
    tmdb_api_key: str = ""
    opensubtitles_api_key: str = ""

    # Subtítulos: lista separada por comas (por ahora solo "en")
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
