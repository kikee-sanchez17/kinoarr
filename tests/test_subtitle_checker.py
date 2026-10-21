from datetime import UTC, datetime, timedelta

from app.clients.opensubtitles import OpenSubtitlesError, QuotaExceededError
from app.clients.qbittorrent import QBittorrentError
from app.models import SubtitleFetchResult, Torrent
from app.services.subtitle_checker import DEFAULT_QUOTA_PAUSE, NOT_FOUND_RETRY, SubtitleChecker
from app.services.subtitle_fetch import SubtitleDownloadsDisabledError, SubtitleNotFoundError

START = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeQBittorrent:
    def __init__(self, torrents: list[Torrent], error: Exception | None = None) -> None:
        self._torrents = torrents
        self._error = error

    def list_torrents(self, completed_only: bool = False) -> list[Torrent]:
        if self._error:
            raise self._error
        assert completed_only
        return self._torrents


class FakeFetchService:
    def __init__(self, errors: dict[str, Exception] | None = None) -> None:
        self.errors = errors or {}
        self.fetched: list[str] = []

    def fetch(self, torrent_hash: str) -> SubtitleFetchResult:
        self.fetched.append(torrent_hash)
        if torrent_hash in self.errors:
            raise self.errors[torrent_hash]
        return SubtitleFetchResult(torrent_hash=torrent_hash, status="downloaded", subtitle_file="Movie.en.srt")


def make_torrent(torrent_hash: str, tags: list[str] | None = None) -> Torrent:
    return Torrent(
        hash=torrent_hash,
        name=f"Movie {torrent_hash}",
        state="uploading",
        progress=1.0,
        size=1_000,
        save_path="/downloads",
        content_path=f"/downloads/{torrent_hash}",
        category="",
        tags=["kinoarr"] if tags is None else tags,
    )


def make_checker(torrents, fetch_service, clock=None, qbittorrent_error=None) -> SubtitleChecker:
    return SubtitleChecker(FakeQBittorrent(torrents, qbittorrent_error), fetch_service, now=clock or Clock())


def test_only_kinoarr_torrents_are_fetched():
    fetch_service = FakeFetchService()
    checker = make_checker([make_torrent("a"), make_torrent("b", tags=["other"])], fetch_service)

    checker.check_once()

    assert fetch_service.fetched == ["a"]


def test_done_torrents_are_not_checked_again():
    fetch_service = FakeFetchService()
    checker = make_checker([make_torrent("a")], fetch_service)

    checker.check_once()
    checker.check_once()

    assert fetch_service.fetched == ["a"]


def test_not_found_is_retried_after_a_day():
    clock = Clock()
    fetch_service = FakeFetchService({"a": SubtitleNotFoundError("none")})
    checker = make_checker([make_torrent("a")], fetch_service, clock)

    checker.check_once()
    clock.advance(NOT_FOUND_RETRY - timedelta(minutes=1))
    checker.check_once()
    clock.advance(timedelta(minutes=1))
    checker.check_once()

    assert fetch_service.fetched == ["a", "a"]


def test_quota_pauses_everything_until_reset():
    clock = Clock()
    reset_at = START + timedelta(hours=3)
    fetch_service = FakeFetchService({"a": QuotaExceededError(reset_at)})
    checker = make_checker([make_torrent("a"), make_torrent("b")], fetch_service, clock)

    checker.check_once()
    assert fetch_service.fetched == ["a"]  # the round stops at the quota error

    clock.advance(timedelta(hours=2))
    checker.check_once()
    assert fetch_service.fetched == ["a"]

    fetch_service.errors.clear()
    clock.advance(timedelta(hours=1))
    checker.check_once()
    assert fetch_service.fetched == ["a", "a", "b"]


def test_quota_without_reset_time_pauses_for_default():
    clock = Clock()
    fetch_service = FakeFetchService({"a": QuotaExceededError(None)})
    checker = make_checker([make_torrent("a")], fetch_service, clock)

    checker.check_once()
    clock.advance(DEFAULT_QUOTA_PAUSE - timedelta(minutes=1))
    checker.check_once()

    assert fetch_service.fetched == ["a"]


def test_one_failing_torrent_does_not_stop_the_others_and_is_retried_next_round():
    fetch_service = FakeFetchService({"a": OpenSubtitlesError("down")})
    checker = make_checker([make_torrent("a"), make_torrent("b")], fetch_service)

    checker.check_once()
    checker.check_once()

    assert fetch_service.fetched == ["a", "b", "a"]


def test_qbittorrent_down_skips_the_round():
    fetch_service = FakeFetchService()
    checker = make_checker([], fetch_service, qbittorrent_error=QBittorrentError("down"))

    checker.check_once()

    assert fetch_service.fetched == []


def test_without_opensubtitles_a_torrent_without_its_own_subtitle_is_retried_after_a_day(caplog):
    clock = Clock()
    fetch_service = FakeFetchService({"a": SubtitleDownloadsDisabledError("set OPENSUBTITLES_API_KEY")})
    checker = make_checker([make_torrent("a")], fetch_service, clock)

    checker.check_once()
    checker.check_once()
    clock.advance(NOT_FOUND_RETRY)
    checker.check_once()

    assert fetch_service.fetched == ["a", "a"]
    assert not any(record.exc_info for record in caplog.records)
