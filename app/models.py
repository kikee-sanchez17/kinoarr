from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.release_title import Resolution, VideoCodec


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
    # Best guesses from the title; None when the title does not say.
    resolution: Resolution | None
    video_codec: VideoCodec | None


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


class SubtitleStream(BaseModel):
    """One embedded subtitle track, as ffprobe reports it."""

    index: int
    codec: str | None
    language: str | None
    title: str | None
    forced: bool
    hearing_impaired: bool


class FoundSubtitle(BaseModel):
    source: Literal["embedded", "sidecar"]
    description: str  # e.g. "track 2 (subrip, eng)" or "Movie.en.srt"


class SubtitleReport(BaseModel):
    torrent_hash: str
    torrent_name: str
    video_path: str
    has_english_subtitle: bool
    english_subtitles: list[FoundSubtitle]


class SubtitleCandidate(BaseModel):
    """An English subtitle file offered by OpenSubtitles."""

    file_id: int
    file_name: str
    download_count: int
    hash_match: bool  # made for this exact release, so its timing fits
    movie_title: str | None = None  # the movie OpenSubtitles files it under
    movie_year: int | None = None


class SubtitleFetchResult(BaseModel):
    torrent_hash: str
    status: Literal["downloaded", "already_present", "copied_from_torrent"]
    subtitle_file: str | None  # name of the saved or copied subtitle
