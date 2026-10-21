from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import qbittorrentapi
from qbittorrentapi.torrents import TorrentsAddedMetadata

from app.models import MagnetLink, Torrent, TorrentFile, TorrentSource
from app.path_mapping import map_path

# Web API before v2.14 answers torrents/add with plain text.
ADD_FAILED_RESPONSE = "Fails."
REJECTED_MESSAGE = "qBittorrent refused the torrent (it may already be in the list)"


class QBittorrentError(Exception):
    """Could not talk to qBittorrent (connection, login or API error)."""


class QBittorrentRejectedError(QBittorrentError):
    """qBittorrent was reached but refused the torrent (e.g. already added, or invalid)."""


class QBittorrentClient:
    """Thin wrapper over qbittorrent-api: translates calls, holds no Kinoarr logic."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        remote_downloads_path: str = "",
        local_downloads_path: str = "",
    ) -> None:
        self._remote_downloads_path = remote_downloads_path
        self._local_downloads_path = local_downloads_path
        self._client = qbittorrentapi.Client(
            host=url,
            username=username,
            password=password,
            REQUESTS_ARGS={"timeout": (5, 15)},
        )

    def version(self) -> str:
        with _translate_errors():
            return self._client.app.version

    def list_torrents(self, completed_only: bool = False, tag: str | None = None) -> list[Torrent]:
        with _translate_errors():
            raw = self._client.torrents_info(status_filter="completed" if completed_only else None, tag=tag)
        return [self._to_torrent(t) for t in raw]

    def get_torrent(self, torrent_hash: str) -> Torrent | None:
        with _translate_errors():
            raw = self._client.torrents_info(torrent_hashes=torrent_hash)
        return self._to_torrent(raw[0]) if raw else None

    def add_torrent(self, source: TorrentSource, tags: list[str]) -> None:
        """Add a torrent; qBittorrent picks the save folder (its default or the category's)."""
        with _translate_errors():
            try:
                response = self._add(source, tags)
            except qbittorrentapi.Conflict409Error as exc:
                raise QBittorrentRejectedError(REJECTED_MESSAGE) from exc
        if _is_rejection(response):
            raise QBittorrentRejectedError(REJECTED_MESSAGE)

    def _add(self, source: TorrentSource, tags: list[str]) -> str | TorrentsAddedMetadata:
        match source:
            case TorrentFile(content=content):
                return self._client.torrents_add(torrent_files=content, tags=tags)
            case MagnetLink(uri=uri):
                return self._client.torrents_add(urls=uri, tags=tags)

    def _to_torrent(self, raw: Any) -> Torrent:
        return Torrent(
            hash=raw.hash,
            name=raw.name,
            state=raw.state,
            progress=raw.progress,
            size=raw.size,
            save_path=self._to_local_path(raw.save_path),
            content_path=self._to_local_path(getattr(raw, "content_path", "")),
            category=raw.category,
            tags=[tag.strip() for tag in raw.tags.split(",") if tag.strip()],
        )

    def _to_local_path(self, qbittorrent_path: str) -> str:
        return map_path(qbittorrent_path, self._remote_downloads_path, self._local_downloads_path)


def _is_rejection(response: str | TorrentsAddedMetadata) -> bool:
    if isinstance(response, str):
        return response == ADD_FAILED_RESPONSE
    # Web API v2.14+ answers with counts instead of "Ok."/"Fails.".
    return response.get("success_count", 0) == 0 and response.get("failure_count", 0) > 0


@contextmanager
def _translate_errors() -> Iterator[None]:
    try:
        yield
    except qbittorrentapi.LoginFailed as exc:
        raise QBittorrentError("qBittorrent login failed: check the username and password") from exc
    except qbittorrentapi.APIConnectionError as exc:
        raise QBittorrentError(f"Cannot connect to qBittorrent: {exc}") from exc
    except qbittorrentapi.APIError as exc:
        raise QBittorrentError(f"qBittorrent API error: {exc}") from exc
