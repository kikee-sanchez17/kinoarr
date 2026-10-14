from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import downloads
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The qBittorrent poller will be started here later.
    yield


app = FastAPI(
    title="Kinoarr",
    description="Unofficial companion app for Jellyfin: search movies, download via qBittorrent, fetch missing subtitles.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(downloads.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def show_config() -> dict:
    """Non-secret settings, useful to check that the .env file is loaded correctly."""
    s = get_settings()
    return {
        "qbittorrent_url": s.qbittorrent_url,
        "jellyfin_url": s.jellyfin_url,
        "prowlarr_url": s.prowlarr_url,
        "subtitle_languages": s.subtitle_language_list,
        "qbittorrent_downloads_path": s.qbittorrent_downloads_path,
        "kinoarr_downloads_path": s.kinoarr_downloads_path,
        "poll_interval": s.poll_interval,
    }