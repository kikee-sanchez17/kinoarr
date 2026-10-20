# Plan: Send a search result to qBittorrent

Implements [spec.md](spec.md).

## Observed behaviour (dev Prowlarr, 2026-10-20)
- `downloadUrl` → `200`, `Content-Type: application/x-bittorrent`, body is the `.torrent` file.
- `magnetUrl` → `301`, `Location: magnet:?xt=urn:btih:...`.
- Prowlarr indexers have a "redirect" option; when on, `downloadUrl` answers with a redirect to the indexer's own `http(s)` URL instead of proxying the file.
- Many results only have `magnetUrl` (all The Pirate Bay results did); some have both.

## Dependencies
None new. `httpx` and `qbittorrent-api` are already used.

## Design

### Models (`app/models.py`)
```python
class TorrentFile(BaseModel):
    """A .torrent file's contents."""
    content: bytes

class MagnetLink(BaseModel):
    """A magnet: URI."""
    uri: str

TorrentSource = TorrentFile | MagnetLink

class DownloadRequest(BaseModel):
    release_id: str = Field(min_length=1)

class DownloadStarted(BaseModel):
    release_id: str
    title: str
```
Two small types instead of one model with two optional fields, so "neither" or "both" cannot be represented.

### `app/clients/prowlarr.py`: `fetch_torrent(download_link: str) -> TorrentSource`
- Requests the link with `follow_redirects=False`, so Kinoarr decides what each redirect means:
  - `200` with a non-empty body → `TorrentFile(content=...)`.
  - `3xx` with `Location` starting with `magnet:` → `MagnetLink(uri=...)`.
  - `3xx` with an `http(s)` `Location` → request that URL, up to `MAX_REDIRECTS = 5` hops.
  - Anything else (other status, empty body, missing `Location`, too many redirects, other scheme) → `ProwlarrError`.
- **The API key header is only sent to Prowlarr.** The first request goes through the existing client (Prowlarr's `base_url` and `X-Api-Key` header). Redirects to another host go through a plain `httpx` request without that header. (The link itself already carries `apikey=` in its query string for Prowlarr; that is fine because it only ever goes to Prowlarr.)
- Timeout `DOWNLOAD_TIMEOUT_SECONDS = 30`: fetching one file should be quick, unlike a search.
- Error messages never include the link (it contains the API key): e.g. "Prowlarr could not provide the torrent: HTTP 404", "Cannot connect to Prowlarr at <PROWLARR_URL>", "Too many redirects while fetching the torrent".
- Why this lives in the Prowlarr client: the link is a Prowlarr endpoint, and the client already owns the connection, API key and error mapping.

### `app/clients/qbittorrent.py`: `add_torrent(source: TorrentSource, tags: list[str]) -> None`
- `TorrentFile` → `torrents_add(torrent_files=content, tags=tags)`; `MagnetLink` → `torrents_add(urls=uri, tags=tags)`. No `save_path`, so qBittorrent uses its default.
- New `QBittorrentRejectedError(QBittorrentError)` when qBittorrent refuses the torrent. Depending on the qBittorrent version this is either a `"Fails."` return value or a `Conflict409Error` (newer Web API); both are handled. Confirm which one the dev qBittorrent uses during the manual check.
- Login and connection errors map to `QBittorrentError` like the existing methods. The three repeated `except` blocks become one private helper/context manager, since this is now the third copy (DRY).
- The client gets no Kinoarr rules: the tag is passed in.

### `app/services/downloads.py`
```python
KINOARR_TAG = "kinoarr"

class ReleaseNotFoundError(Exception): ...

class DownloadService:
    def __init__(self, release_store, prowlarr_client, qbittorrent_client) -> None: ...
    def start_download(self, release_id: str) -> DownloadStarted:
        # 1. look up the release (ReleaseNotFoundError if missing)
        # 2. pick download_url, else magnet_url
        # 3. prowlarr_client.fetch_torrent(link)
        # 4. qbittorrent_client.add_torrent(source, tags=[KINOARR_TAG])
```
- Kinoarr's rules (which link to prefer, which tag) live here; both clients stay translators.
- Logs one info line with the release ID and title when a download starts (never the link).

### `app/api/downloads.py`
- `POST /api/downloads`, body `DownloadRequest`, `status_code=202`, `response_model=DownloadStarted`.
- Error mapping, in this order (the subclass before its parent):
  | Exception | HTTP |
  |---|---|
  | `ReleaseNotFoundError` | 404 "Release not found: search again" |
  | `QBittorrentRejectedError` | 409 |
  | `ProwlarrError`, `QBittorrentError` | 502 |

### `app/dependencies.py`
- `get_download_service()` with `@lru_cache`, built from the existing shared client and store getters.

## Testing strategy
- `tests/test_prowlarr_client.py` (respx):
  - `200` body → `TorrentFile`; `301` to `magnet:` → `MagnetLink`.
  - `301` to an external `http` URL is followed, and that second request has **no** `X-Api-Key` header.
  - Too many redirects, non-magnet/non-http scheme, missing `Location`, empty body, `404`, connection error, timeout → `ProwlarrError`; the API key is not in the message.
- `tests/test_qbittorrent_client.py` (fake `qbittorrentapi` client as today):
  - `TorrentFile` passes `torrent_files`, `MagnetLink` passes `urls`; tags passed through; no `save_path`.
  - `"Fails."` and `Conflict409Error` → `QBittorrentRejectedError`; connection/login errors → `QBittorrentError`.
- `tests/test_download_service.py` (fakes): unknown ID → `ReleaseNotFoundError`; `download_url` preferred over `magnet_url`; magnet used when it is the only link; tag `kinoarr` passed; returns ID and title.
- `tests/test_downloads.py`: `202` with body; `404`, `409`, `502` (both clients), `422` for empty/missing `release_id`.

## Manual check (legal content only)
The dev Prowlarr now also has The Pirate Bay and YTS. **Only Internet Archive results are sent to qBittorrent.** The magnet path is covered by unit tests; it is checked manually only if an Internet Archive result offers a magnet link.

## Risks / notes
- Some indexers redirect to sites that need cookies or block unknown User-Agents; those show up as `502` with the HTTP status, which is the best Kinoarr can do without per-indexer logic.
- Tag creation: qBittorrent creates a tag automatically when a torrent is added with it, so no setup step is needed (verify in the manual check).
