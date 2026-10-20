# Plan: Subtitle download and background checker

Implements [spec.md](spec.md).

## OpenSubtitles API used
Base URL `https://api.opensubtitles.com/api/v1`. Every request sends `Api-Key: <key>` and `User-Agent: Kinoarr v<version>` (the API blocks generic user agents).

| Call | Purpose |
|---|---|
| `POST /login` `{username, password}` | Optional. Returns `token` (sent as `Authorization: Bearer`) and `base_url` (logged-in users may be told to use another host, e.g. a VIP one). |
| `GET /subtitles?languages=en&moviehash=...` or `...&query=...` with `type=movie&hearing_impaired=exclude&foreign_parts_only=exclude` | Search. Parameters sent sorted and lowercase, as the API asks (otherwise it answers with a redirect). Returns `data[].attributes` with `language`, `download_count`, `hearing_impaired`, `foreign_parts_only`, `moviehash_match`, `files[{file_id, file_name}]`. |
| `POST /download` `{file_id, sub_format: "srt"}` | Returns a temporary `link` to the file plus `remaining` and `reset_time_utc`. `406` when the daily quota is used up. |
| `GET <link>` | The `.srt` content. |

Confirmed against the real API (task 1, 2026-10-20):
- The search URL must be in the API's normalised form (parameters sorted, lowercase, spaces as `+`), otherwise it answers `301`. httpx already encodes spaces as `+`.
- Search attributes include `language`, `download_count`, `hearing_impaired`, `foreign_parts_only`, `ai_translated`, `machine_translated`, `moviehash_match` (only meaningful in hash searches), `release`, `files[{file_id, cd_number, file_name}]`. Some results have several files (CDs).
- Rate limit headers: 5 requests per second.
- `POST /login` returns `user.allowed_downloads` (20 for a free "Sub leecher" account), `token`, `base_url` (`api.opensubtitles.com`).
- `POST /download` returns `link`, `file_name`, `requests`, `remaining`, `message`, `reset_time`, `reset_time_utc`. The `link` serves the `.srt` directly (`200`, `text/plain`).

Additions after task 1:
- AI-translated and machine-translated subtitles are skipped (quality), like HI and forced ones.
- `app/main.py` configures logging (`INFO`) so the checker's lines are visible, and sets the `httpx` logger to `WARNING`: at `INFO` httpx logs every request URL, and Prowlarr download links carry the API key.

## Dependencies
None new (`httpx`, standard library).

## Configuration
- `app/config.py`: `opensubtitles_username: str = ""`, `opensubtitles_password: str = ""`.
- `.env.example`: both, commented as optional (higher daily quota).

## Design

### `app/movie_hash.py`: OpenSubtitles file hash (pure)
- `movie_hash(video_path: Path) -> str | None`: file size + the sum of the first and last 64 KiB read as little-endian 64-bit integers, modulo 2^64, as 16 hex digits. `None` for files under 128 KiB (the algorithm needs both chunks).
- Tested against the reference value OpenSubtitles publishes for its test file, plus a generated file.

### Models (`app/models.py`)
```python
class SubtitleCandidate(BaseModel):
    file_id: int
    file_name: str
    download_count: int
    hash_match: bool

class SubtitleFetchResult(BaseModel):
    torrent_hash: str
    status: Literal["downloaded", "already_present"]
    subtitle_file: str | None     # name of the saved .srt
```

### `app/clients/opensubtitles.py`
- `OpenSubtitlesError(Exception)`; `QuotaExceededError(OpenSubtitlesError)` with `reset_at: datetime | None`.
- `OpenSubtitlesClient(api_key, username, password, app_version)`:
  - `search_english(movie_hash: str | None, query: str | None) -> list[SubtitleCandidate]`: one search; drops HI/forced and multi-file results (kept as a safety net even though the query excludes them).
  - `download(file_id: int) -> bytes`: `POST /download`, then fetches the `link`.
  - Login is lazy (first request) and the token is reused; on `401` it logs in again once. Without username/password it never logs in.
  - Error mapping: `401/403` → "API key or login rejected", `406` / `remaining == 0` → `QuotaExceededError` (with `reset_time_utc`), `429` → "rate limited", connection/timeout → "cannot connect", bad JSON → "unexpected response". Messages never contain the key, password or token.
  - Timeout constant `REQUEST_TIMEOUT_SECONDS = 30`.

### `app/subtitles.py`: add
- `english_sidecar_path(video_path: Path) -> Path`: `<stem>.en.srt` (constant `DOWNLOADED_SUBTITLE_SUFFIX = ".en.srt"`); `is_english_sidecar` already accepts it.
- `best_candidate(candidates) -> SubtitleCandidate | None`: hash matches first, then highest `download_count`.

### `app/services/subtitle_fetch.py`
```python
class SubtitleNotFoundError(Exception): ...
class SubtitleDownloadsDisabledError(Exception): ...
class SubtitleWriteError(Exception): ...

class SubtitleFetchService:
    def __init__(self, detection_service, opensubtitles_client | None) -> None: ...
    def fetch(self, torrent_hash: str) -> SubtitleFetchResult:
        # under a lock (one download at a time):
        # 1. detection_service.detect(hash); already English → already_present
        # 2. search by movie_hash(video); if empty, search by torrent name
        # 3. best_candidate → SubtitleNotFoundError if None
        # 4. download → write <stem>.en.srt via a ".part" temp file + Path.replace
```
- `SubtitleDetectionService.detect` already returns the video path; the torrent name for the text search needs the `Torrent`, so `detect` gets a small sibling `inspect(hash) -> (Torrent, Path, SubtitleReport)` or the report gains `torrent_name`. **Choice: add `torrent_name` to `SubtitleReport`** (useful in the API too, no extra method).
- `opensubtitles_client is None` (no API key) → `SubtitleDownloadsDisabledError`.
- Write errors (`OSError`) → `SubtitleWriteError("Cannot write <file>: check that Kinoarr can write to the downloads folder (PUID/PGID)")`; the `.part` file is removed on failure.

### `app/services/subtitle_checker.py`
```python
NOT_FOUND_RETRY = timedelta(hours=24)
DEFAULT_QUOTA_PAUSE = timedelta(hours=24)

class SubtitleChecker:
    def __init__(self, qbittorrent_client, fetch_service, now: Callable[[], datetime] = utc_now) -> None: ...
    def check_once(self) -> None:
        # skip everything while paused for quota
        # for each completed torrent tagged KINOARR_TAG, not done, not waiting for retry:
        #   fetch → mark done; SubtitleNotFoundError → retry in 24 h;
        #   QuotaExceededError → pause until reset, stop this round;
        #   other errors → log warning, try next round
```
- `now` is injected so tests control time without sleeping.
- The tag constant moves to a shared place (`app/services/downloads.py` already has `KINOARR_TAG`; the checker imports it).

### Running the checker (`app/main.py` lifespan)
```python
async def run_checker(checker, interval_seconds):
    while True:
        await asyncio.to_thread(checker.check_once)   # sync code, off the event loop
        await asyncio.sleep(interval_seconds)
```
- Started as an `asyncio` task in `lifespan` only when `OPENSUBTITLES_API_KEY` is set; cancelled on shutdown. `check_once` catches its own errors, and the loop also logs any unexpected exception and keeps going.
- Why `asyncio.to_thread`: the clients are blocking (httpx sync, subprocess); running them on the event loop would freeze the API.
- Unit tests do not start it: `TestClient(app)` without `with` skips the lifespan.

### `app/api/downloads.py`
- `POST /api/downloads/{torrent_hash}/subtitles`, `response_model=SubtitleFetchResult`. Error table as in the spec (`429`, `503` new).
- Detection error mapping is shared between GET and POST via one small helper to avoid duplicating the table.

### `app/dependencies.py`
- `get_opensubtitles_client() -> OpenSubtitlesClient | None` (None without an API key), `get_subtitle_fetch_service()`, `get_subtitle_checker()`.

## Testing strategy
- `tests/test_movie_hash.py`: reference value; small file → `None`.
- `tests/test_opensubtitles_client.py` (respx): headers (Api-Key, User-Agent, no auth when anonymous), sorted lowercase params, filtering, login only when configured, token reuse, re-login on 401, `406` → `QuotaExceededError` with reset time, other errors, secrets never in messages.
- `tests/test_subtitles.py`: `english_sidecar_path`, `best_candidate`.
- `tests/test_subtitle_fetch_service.py`: already present (no search), hash search used first, name fallback, not found, disabled, file written with `.en.srt` and no `.part` left, write failure cleans up.
- `tests/test_subtitle_checker.py`: only finished `kinoarr` torrents; done torrents skipped; 24 h retry; quota pause until reset; one failing torrent does not stop others.
- `tests/test_downloads.py`: POST route status codes.

## Manual check (frugal with quota)
1. User creates an API key (and optionally sets username/password) in `.env`.
2. Task 1: one search call and one download call to confirm the field names.
3. On the Internet Archive trailer (or another finished Internet Archive download): POST → `downloaded`, `.srt` present, GET → `true`; POST again → `already_present`.
4. Checker: delete that `.srt`, set a short `POLL_INTERVAL` for the run, see it re-fetched once and left alone afterwards.
5. No API key → POST `503`, log line about the disabled checker.
Total: about 3 downloads.

## Risks / notes
- The trailer is stuck at 98% in qBittorrent, so it is not "finished"; the manual check needs a finished Internet Archive download (or the trailer completed). To sort out at task 1.
- Remembered API details may be off; task 1 exists for that.
