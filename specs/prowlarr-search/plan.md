# Plan: Prowlarr movie search

Implements [spec.md](spec.md).

## Dev environment
Add a `prowlarr` service to `docker-compose.dev.yml`, following the existing qBittorrent service:
- image `lscr.io/linuxserver/prowlarr:latest`, `PUID`/`PGID`/`TZ` like qBittorrent
- port `9696:9696`
- config volume `./dev-config/prowlarr:/config` (already git-ignored via `dev-config/`)

Manual setup in the Prowlarr web UI:
1. Add the **Internet Archive** indexer (public, no account, public-domain movies: legal test content).
2. Copy the API key from *Settings → General* into `.env` as `PROWLARR_API_KEY`, and set `PROWLARR_URL=http://localhost:9696`.

## Prowlarr API used
```
GET {PROWLARR_URL}/api/v1/search?query=<text>&type=search&categories=2000
Header: X-Api-Key: <PROWLARR_API_KEY>
```
Returns a JSON array of releases. Fields used (camelCase in Prowlarr's JSON):
`guid`, `title`, `indexer`, `size`, `seeders`, `leechers`, `publishDate`, `downloadUrl`, `magnetUrl`, `infoUrl`, `protocol`.

`type=search` (free-text) is used instead of `type=movie`, because not every indexer supports movie-specific search; the category filter already restricts results to movies.

Field names and types confirmed against Prowlarr's OpenAPI schema (`ReleaseResource`). Nullable fields: `guid`, `title`, `indexer`, `seeders`, `leechers`, `downloadUrl`, `magnetUrl`, `infoUrl`. `protocol` is one of `unknown`, `usenet`, `torrent`.

Observed against the real instance: when an indexer fails, Prowlarr still answers `200` with an empty list, and a search can take ~100 s.

## Dependencies
None new. `httpx` (runtime) and `respx` (tests) are already in the requirements.

## Design

### Why download links stay on the server
Prowlarr's `downloadUrl` and `magnetUrl` both look like
`{PROWLARR_URL}/{indexerId}/download?apikey=<PROWLARR_API_KEY>&link=...`: anyone holding one can use Prowlarr's API key. So the browser only gets a result ID, and the backend keeps the links. `magnetUrl` is also a Prowlarr link, not a `magnet:` URI.

### `app/models.py`: two models
```python
class Release(BaseModel):
    """A Prowlarr search result as Kinoarr's backend sees it (includes download links)."""
    id: str
    title: str
    indexer: str
    size: int                 # bytes
    seeders: int | None
    leechers: int | None
    publish_date: datetime
    info_url: str | None
    download_url: str | None
    magnet_url: str | None


class SearchResult(BaseModel):
    """What the API returns: a Release without its download links."""
    id: str
    title: str
    indexer: str
    size: int
    seeders: int | None
    leechers: int | None
    publish_date: datetime
    info_url: str | None
```
- `id` is a short hash (SHA-256, first 16 hex chars) of Prowlarr's `guid`. The `guid` itself is not exposed because on some indexers it is the download link itself (possibly with a tracker passkey).
- Our API uses snake_case like the rest of Kinoarr; the client translates from Prowlarr's camelCase, which keeps Prowlarr's naming out of our public API.

### `app/clients/prowlarr.py`
- `ProwlarrError(Exception)`: any failure talking to Prowlarr.
- `ProwlarrClient(url, api_key)`:
  - owns an `httpx.Client` with `base_url`, the `X-Api-Key` header and a timeout constant (`SEARCH_TIMEOUT_SECONDS = 120`: just above Prowlarr's own ~100 s indexer timeout, so Prowlarr always answers first).
  - `search_movies(query: str) -> list[Release]`: sends the request, maps errors, drops non-torrent results and results with no `downloadUrl` and no `magnetUrl`, converts each release to `Release`.
  - A release that fails validation (e.g. missing `title`) is skipped and logged as a warning with its title; the rest of the search still succeeds.
  - If the whole response is not a JSON list, that is a `ProwlarrError` (unexpected response).
- Error mapping (all raise `ProwlarrError`, never including the API key):
  | Situation | Message |
  |---|---|
  | `401` | API key rejected: check `PROWLARR_API_KEY` |
  | other 4xx/5xx | Prowlarr returned HTTP `<code>` |
  | connection error | cannot connect to Prowlarr at `<url>` |
  | timeout | Prowlarr search timed out |
  | invalid JSON / not a list | unexpected response from Prowlarr |
- The client stays a thin translator: no sorting, no storage.

### `app/services/release_store.py`
- `ReleaseStore`: in-memory store of recent releases, keyed by `id`.
  - `add(releases: list[Release]) -> None`
  - `get(release_id: str) -> Release | None` (used by the next implementation, send-to-qBittorrent)
- Bounded so memory cannot grow forever: keeps at most `MAX_STORED_RELEASES = 1000`; when full, the oldest are removed first (`collections.OrderedDict`). Several users or tabs searching at once do not wipe each other's results.
- A `threading.Lock` guards it, because FastAPI runs sync routes in a thread pool.

### `app/services/search.py`
- `SearchService(prowlarr_client, release_store)`:
  - `search_movies(query) -> list[SearchResult]`: calls the client, sorts by seeders descending (unknown seeders last), stores the releases, and returns them converted to `SearchResult` (links stripped).
- This is where Kinoarr's search rules live, so the route stays thin and the client stays a translator.

### `app/api/search.py`
- `GET /api/search`, `query: str = Query(min_length=1)`, `response_model=list[SearchResult]`.
- Calls `SearchService.search_movies`, maps `ProwlarrError` to `502`.

### `app/dependencies.py`
- `get_prowlarr_client()`, `get_release_store()` and `get_search_service()`, each with `@lru_cache` so there is one shared instance (the store must be shared to be useful). Built from the existing `prowlarr_url` and `prowlarr_api_key` settings.

### `app/main.py`
- `app.include_router(search.router)`.

## Testing strategy
- `tests/test_prowlarr_client.py`: HTTP mocked with `respx`.
  - Request has the right path, `query`, `type`, `categories` and `X-Api-Key` header.
  - JSON is converted into `Release`, including releases with no `magnetUrl`/`infoUrl`/`seeders`; `id` is stable for the same `guid`.
  - Usenet releases and releases with no download link are dropped.
  - A malformed release is skipped; the others are still returned.
  - `401`, `500`, connection error, timeout and invalid JSON each raise `ProwlarrError`; the API key is not in the message.
- `tests/test_release_store.py`: add/get, unknown id returns `None`, oldest entries evicted past the limit.
- `tests/test_search_service.py`: sorted by seeders (unknown last), releases stored, returned results have no links.
- `tests/test_search.py`: route tests with a fake service (same style as `test_downloads.py`).
  - `200` with results; the JSON contains no `apikey` and no `download_url`/`magnet_url` keys.
  - `ProwlarrError` → `502`.
  - Empty query → `422`.
- Manual check against the dev Prowlarr (see spec acceptance criteria).

## Risks / notes
- Dev environment: with Cloudflare WARP on, archive.org hangs requests with Prowlarr's User-Agent. Turn WARP off (or exclude archive.org) for manual checks. After toggling WARP, restart the Prowlarr container so it picks up the new DNS servers.
- Prowlarr's `downloadUrl` points back to Prowlarr itself. Passing it straight to qBittorrent can fail if qBittorrent cannot reach that URL (e.g. `localhost` in dev means the qBittorrent container itself). To be decided in the next implementation (send-to-qBittorrent); this one only stores the URLs.
