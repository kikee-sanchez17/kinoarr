from datetime import datetime

from pydantic import BaseModel, Field


class Torrent(BaseModel):
    """Simplified view of a qBittorrent torrent."""

    hash: str
    name: str
    state: str
    progress: float  # 0.0 - 1.0
    size: int  # bytes
    save_path: str
    content_path: str
    category: str
    tags: list[str]

class Release(BaseModel):
    """A Prowlarr search result as Kinoarr's backend sees it (includes download links)."""

    id: str
    title: str
    indexer: str
    size: int  # bytes
    seeders: int | None
    leechers: int | None
    publish_date: datetime
    info_url: str | None
    download_url: str | None
    magnet_url: str | None


class SearchResult(BaseModel):
    """What the API returns: a Release without its download links, which embed Prowlarr's API key."""

    id: str
    title: str
    indexer: str
    size: int  # bytes
    seeders: int | None
    leechers: int | None
    publish_date: datetime
    info_url: str | None


class TorrentFile(BaseModel):
    """A .torrent file's contents."""

    content: bytes


class MagnetLink(BaseModel):
    """A magnet: URI."""

    uri: str


# Two types rather than one model with two optional fields, so "neither" or "both" cannot happen.
TorrentSource = TorrentFile | MagnetLink


class DownloadRequest(BaseModel):
    release_id: str = Field(min_length=1)


class DownloadStarted(BaseModel):
    release_id: str
    title: str
