from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api import downloads

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Aquí se arrancará el poller de qBittorrent más adelante (paso 7).
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
    """Configuración no sensible, útil para comprobar que el .env se carga bien."""
    s = get_settings()
    return {
        "qbit_url": s.qbit_url,
        "jellyfin_url": s.jellyfin_url,
        "prowlarr_url": s.prowlarr_url,
        "subtitle_languages": s.subtitle_language_list,
        "downloads_path": s.downloads_path,
        "poll_interval": s.poll_interval,
    }