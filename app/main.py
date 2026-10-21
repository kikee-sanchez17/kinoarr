import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api import downloads, search
from app.config import APP_VERSION, get_settings
from app.dependencies import get_subtitle_checker
from app.services.subtitle_checker import run_periodically

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# At INFO, httpx logs every request URL, and Prowlarr download links carry the API key.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    checker_task = _start_subtitle_checker()
    yield
    if checker_task:
        checker_task.cancel()
        with suppress(asyncio.CancelledError):
            await checker_task


def _start_subtitle_checker() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.opensubtitles_api_key:
        logger.warning("OPENSUBTITLES_API_KEY is not set: the subtitle checker is disabled")
        return None
    logger.info("Subtitle checker started (every %s s)", settings.poll_interval)
    return asyncio.create_task(run_periodically(get_subtitle_checker(), settings.poll_interval))


app = FastAPI(
    title="Kinoarr",
    description=(
        "Unofficial companion app for Jellyfin: search movies, download via qBittorrent, fetch missing subtitles."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)

app.include_router(downloads.router)
app.include_router(search.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def show_config() -> dict:
    """Non-secret settings, useful to check that the .env file is loaded correctly."""
    s = get_settings()
    return {
        "qbittorrent_url": s.qbittorrent_url,
        "prowlarr_url": s.prowlarr_url,
        "qbittorrent_downloads_path": s.qbittorrent_downloads_path,
        "kinoarr_downloads_path": s.kinoarr_downloads_path,
        "poll_interval": s.poll_interval,
    }
