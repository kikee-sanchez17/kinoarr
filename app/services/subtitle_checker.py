import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.clients.opensubtitles import QuotaExceededError
from app.clients.qbittorrent import QBittorrentClient, QBittorrentError
from app.models import Torrent
from app.services.downloads import KINOARR_TAG
from app.services.subtitle_detection import VideoNotFoundError
from app.services.subtitle_fetch import SubtitleFetchService, SubtitleNotFoundError

logger = logging.getLogger(__name__)

# Waiting this long before asking again gives new subtitles time to be uploaded.
NOT_FOUND_RETRY = timedelta(hours=24)
# Used when OpenSubtitles does not say when the quota resets.
DEFAULT_QUOTA_PAUSE = timedelta(hours=24)


def utc_now() -> datetime:
    return datetime.now(UTC)


class SubtitleChecker:
    """Fetches missing subtitles for finished Kinoarr downloads, one round per call.

    Its memory (done torrents, retry times, quota pause) lives only in this
    object, so a restart simply retries everything once.
    """

    def __init__(
        self,
        qbittorrent_client: QBittorrentClient,
        fetch_service: SubtitleFetchService,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._qbittorrent_client = qbittorrent_client
        self._fetch_service = fetch_service
        self._now = now
        self._done: set[str] = set()
        self._retry_at: dict[str, datetime] = {}
        self._paused_until: datetime | None = None

    def check_once(self) -> None:
        now = self._now()
        if self._paused_until and now < self._paused_until:
            return
        try:
            torrents = self._qbittorrent_client.list_torrents(completed_only=True)
        except QBittorrentError as exc:
            logger.warning("Subtitle check skipped: %s", exc)
            return

        for torrent in torrents:
            if not self._is_due(torrent, now):
                continue
            try:
                self._check_torrent(torrent, now)
            except QuotaExceededError as exc:
                self._paused_until = exc.reset_at or now + DEFAULT_QUOTA_PAUSE
                logger.warning("%s: pausing subtitle downloads until %s", exc, self._paused_until)
                return

    def _is_due(self, torrent: Torrent, now: datetime) -> bool:
        if KINOARR_TAG not in torrent.tags or torrent.hash in self._done:
            return False
        retry_at = self._retry_at.get(torrent.hash)
        return retry_at is None or now >= retry_at

    def _check_torrent(self, torrent: Torrent, now: datetime) -> None:
        try:
            self._fetch_service.fetch(torrent.hash)
            self._done.add(torrent.hash)
            self._retry_at.pop(torrent.hash, None)
        except (SubtitleNotFoundError, VideoNotFoundError) as exc:
            self._retry_at[torrent.hash] = now + NOT_FOUND_RETRY
            logger.info("%s; retrying after %s", exc, self._retry_at[torrent.hash])
        except QuotaExceededError:
            raise
        except Exception:
            # One broken torrent must not stop the round for the others; it is retried next round.
            logger.exception("Subtitle check failed for torrent %r", torrent.name)


async def run_periodically(checker: SubtitleChecker, interval_seconds: int) -> None:
    """Run a check round every `interval_seconds` until cancelled."""
    while True:
        try:
            # The clients block (HTTP, ffprobe), so the round runs in a thread to keep the API responsive.
            await asyncio.to_thread(checker.check_once)
        except Exception:
            logger.exception("Subtitle check round failed")
        await asyncio.sleep(interval_seconds)
