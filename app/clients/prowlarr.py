import hashlib
import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.models import MagnetLink, Release, TorrentFile, TorrentSource

logger = logging.getLogger(__name__)

SEARCH_PATH = "/api/v1/search"
MOVIES_CATEGORY = 2000
FREE_TEXT_SEARCH_TYPE = "search"
TORRENT_PROTOCOL = "torrent"
RELEASE_ID_LENGTH = 16

# Just above Prowlarr's own ~100 s indexer timeout, so Prowlarr always answers first.
SEARCH_TIMEOUT_SECONDS = 120

# Fetching a single .torrent file should be quick, unlike a search.
DOWNLOAD_TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
MAGNET_PREFIX = "magnet:"
HTTP_SCHEMES = {"http", "https"}


class ProwlarrError(Exception):
    """Could not talk to Prowlarr (connection, API key, HTTP or response error)."""


class _ProwlarrRelease(BaseModel):
    """One release exactly as Prowlarr's JSON describes it (camelCase on the wire)."""

    model_config = ConfigDict(alias_generator=to_camel)

    guid: str
    title: str
    indexer: str
    size: int
    seeders: int | None = None
    leechers: int | None = None
    publish_date: datetime
    info_url: str | None = None
    download_url: str | None = None
    magnet_url: str | None = None
    protocol: str

    @property
    def is_downloadable_torrent(self) -> bool:
        return self.protocol == TORRENT_PROTOCOL and bool(self.download_url or self.magnet_url)

    def to_release(self) -> Release:
        return Release(
            id=_release_id(self.guid),
            title=self.title,
            indexer=self.indexer,
            size=self.size,
            seeders=self.seeders,
            leechers=self.leechers,
            publish_date=self.publish_date,
            info_url=self.info_url,
            download_url=self.download_url,
            magnet_url=self.magnet_url,
        )


class ProwlarrClient:
    """Thin wrapper over Prowlarr's search API: translates calls, holds no Kinoarr logic."""

    def __init__(self, url: str, api_key: str) -> None:
        self._url = url
        self._client = httpx.Client(
            base_url=url,
            headers={"X-Api-Key": api_key},
            timeout=SEARCH_TIMEOUT_SECONDS,
        )

    def search_movies(self, query: str) -> list[Release]:
        raw_releases = self._get_search_results(query)
        releases = (_parse_release(raw) for raw in raw_releases)
        return [release.to_release() for release in releases if release and release.is_downloadable_torrent]

    def _get_search_results(self, query: str) -> list[Any]:
        params = {"query": query, "type": FREE_TEXT_SEARCH_TYPE, "categories": MOVIES_CATEGORY}
        try:
            response = self._client.get(SEARCH_PATH, params=params)
        except httpx.TimeoutException as exc:
            raise ProwlarrError("Prowlarr search timed out") from exc
        except httpx.TransportError as exc:
            raise ProwlarrError(f"Cannot connect to Prowlarr at {self._url}") from exc

        if response.status_code == httpx.codes.UNAUTHORIZED:
            raise ProwlarrError("Prowlarr rejected the API key: check PROWLARR_API_KEY")
        if response.is_error:
            raise ProwlarrError(f"Prowlarr returned HTTP {response.status_code}")

        try:
            raw_releases = response.json()
        except ValueError as exc:
            raise ProwlarrError("Unexpected response from Prowlarr: not valid JSON") from exc
        if not isinstance(raw_releases, list):
            raise ProwlarrError("Unexpected response from Prowlarr: expected a list of releases")
        return raw_releases

    def fetch_torrent(self, download_link: str) -> TorrentSource:
        """Open a release's Prowlarr link and return the .torrent file or magnet link behind it.

        Redirects are followed by hand: a redirect to `magnet:` is the answer
        itself, and redirects to an indexer's site must not carry the API key header.
        """
        response = self._get_download(download_link, to_prowlarr=True)
        redirects_followed = 0
        while response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                raise ProwlarrError(f"Could not fetch the torrent: HTTP {response.status_code} without a redirect target")
            if location.startswith(MAGNET_PREFIX):
                return MagnetLink(uri=location)
            if redirects_followed == MAX_REDIRECTS:
                raise ProwlarrError("Too many redirects while fetching the torrent")
            next_url = response.url.join(location)
            if next_url.scheme not in HTTP_SCHEMES:
                raise ProwlarrError(f"Unexpected redirect to a {next_url.scheme!r} link while fetching the torrent")
            response = self._get_download(next_url, to_prowlarr=False)
            redirects_followed += 1
        return _torrent_file_from(response)

    def _get_download(self, url: str | httpx.URL, to_prowlarr: bool) -> httpx.Response:
        # Error messages never include the URL: Prowlarr links embed the API key.
        get = self._client.get if to_prowlarr else httpx.get
        try:
            return get(url, follow_redirects=False, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        except httpx.TimeoutException as exc:
            raise ProwlarrError("Timed out while fetching the torrent") from exc
        except httpx.TransportError as exc:
            if to_prowlarr:
                raise ProwlarrError(f"Cannot connect to Prowlarr at {self._url}") from exc
            raise ProwlarrError(f"Cannot connect to {httpx.URL(url).host} while fetching the torrent") from exc


def _torrent_file_from(response: httpx.Response) -> TorrentFile:
    if response.status_code != httpx.codes.OK:
        raise ProwlarrError(f"Could not fetch the torrent: HTTP {response.status_code}")
    if not response.content:
        raise ProwlarrError("Could not fetch the torrent: empty response")
    return TorrentFile(content=response.content)


def _parse_release(raw: Any) -> _ProwlarrRelease | None:
    """Parse one release, or return None (with a warning) if it is malformed."""
    try:
        return _ProwlarrRelease.model_validate(raw)
    except ValidationError as exc:
        # Only field names are logged: the error's input values can include
        # download URLs, which embed Prowlarr's API key.
        title = raw.get("title") if isinstance(raw, dict) else None
        invalid_fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        logger.warning("Skipping malformed Prowlarr release %r: invalid fields %s", title, invalid_fields)
        return None


def _release_id(guid: str) -> str:
    # A hash, not the guid itself: on some indexers the guid is the download link (with a passkey).
    return hashlib.sha256(guid.encode()).hexdigest()[:RELEASE_ID_LENGTH]
