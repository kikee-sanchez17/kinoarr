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

### `app/models.py`: new `SearchResult`
```python
class SearchResult(BaseModel):
    guid: str
    title: str
    indexer: str
    size: int                 # bytes
    seeders: int | None
    leechers: int | None
    publish_date: datetime
    download_url: str | None
    magnet_url: str | None
    info_url: str | None
```
Our API uses snake_case like the rest of Kinoarr; the client translates from Prowlarr's camelCase. That keeps Prowlarr's naming out of our public API, so we can change provider without changing the API.

### `app/clients/prowlarr.py`
- `ProwlarrError(Exception)`: any failure talking to Prowlarr.
- `ProwlarrClient(url, api_key)`:
  - owns an `httpx.Client` with `base_url`, the `X-Api-Key` header and a timeout constant (`SEARCH_TIMEOUT_SECONDS = 120`: just above Prowlarr's own ~100 s indexer timeout, so Prowlarr always answers first).
  - `search_movies(query: str) -> list[SearchResult]`: sends the request, maps errors, drops non-torrent results and results with no `downloadUrl` and no `magnetUrl`, converts each release to `SearchResult`.
  - A release that fails validation (e.g. missing `title`) is skipped and logged as a warning with its title/guid; the rest of the search still succeeds.
  - If the whole response is not a JSON list, that is a `ProwlarrError` (unexpected response).
- Error mapping (all raise `ProwlarrError`, never including the API key):
  | Situation | Message |
  |---|---|
  | `401` | API key rejected: check `PROWLARR_API_KEY` |
  | other 4xx/5xx | Prowlarr returned HTTP `<code>` |
  | connection error | cannot connect to Prowlarr at `<url>` |
  | timeout | Prowlarr search timed out |
  | invalid JSON / not a list | unexpected response from Prowlarr |
- The client stays a thin translator: no sorting or business rules.

### `app/api/search.py`
- `GET /api/search`, `query: str = Query(min_length=1)`, `response_model=list[SearchResult]`.
- Calls `search_movies`, sorts by seeders descending (unknown seeders last), maps `ProwlarrError` to `502`.
- Sorting is one line, so it lives in the route rather than in a new service module (YAGNI). If more search logic shows up later, it moves into `app/services/`.

### `app/dependencies.py`
- `get_prowlarr_client()` with `@lru_cache`, built from `prowlarr_url` and `prowlarr_api_key` settings (already exist in `config.py`).

### `app/main.py`
- `app.include_router(search.router)`.

## Testing strategy
- `tests/test_prowlarr_client.py`: HTTP mocked with `respx`.
  - Request has the right path, `query`, `type`, `categories` and `X-Api-Key` header.
  - JSON is converted into `SearchResult`, including releases with no `magnetUrl`/`infoUrl`/`seeders`.
  - Usenet releases and releases with no download link are dropped.
  - A malformed release is skipped; the others are still returned.
  - `401`, `500`, connection error, timeout and invalid JSON each raise `ProwlarrError`; the API key is not in the message.
- `tests/test_search.py`: route tests with a fake client (same style as `test_downloads.py`).
  - `200` with results sorted by seeders, unknown seeders last.
  - `ProwlarrError` → `502`.
  - Empty query → `422`.
- Manual check against the dev Prowlarr (see spec acceptance criteria).

## Risks / notes
- Dev environment: with Cloudflare WARP on, archive.org hangs requests with Prowlarr's User-Agent. Turn WARP off (or exclude archive.org) for manual checks. After toggling WARP, restart the Prowlarr container so it picks up the new DNS servers.
- Prowlarr's `downloadUrl` points back to Prowlarr itself. Passing it straight to qBittorrent can fail if qBittorrent cannot reach that URL (e.g. `localhost` in dev means the qBittorrent container itself). To be decided in the next implementation (send-to-qBittorrent); this one only exposes the URLs.
