# Plan: Simple web UI

Implements [spec.md](spec.md).

## Dependencies
- None new. FastAPI's `StaticFiles` (from Starlette, already installed) serves the page.
- Remove `jinja2` from `requirements.txt`: nothing imports it, and the UI does not use templates.

## Design

### Backend: tag filter
- `QBittorrentClient.list_torrents(completed_only: bool = False, tag: str | None = None)` passes `tag` to `torrents_info(tag=...)`. qBittorrent does the filtering (Web API 2.8.3+, which every supported version has). The client stays a translator: it knows nothing about `kinoarr`.
- `GET /api/downloads` gains `tag: str | None = None` and passes it through. `?completed=true&tag=kinoarr` combines both.
- The subtitle checker keeps filtering by tag itself; changing it is not needed for this feature.

### Backend: serving the page
- Static files live in `app/static/`: `index.html`, `app.js`, `style.css`. Inside `app/`, so the Dockerfile's `COPY app ./app` already ships them.
- In `app/main.py`, after the API routers:
  ```python
  STATIC_DIR = Path(__file__).parent / "static"
  app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
  ```
  - Mounted last: FastAPI checks routes in order, so `/health`, `/api/...`, `/docs` and `/openapi.json` match first, and only remaining paths fall through to the static files.
  - `html=True` serves `index.html` for `/`.
  - The path is built from `__file__`, not the working directory, so it works under `uvicorn` from the repo root, in Docker, and on Windows.

### Frontend (`app/static/`)
No framework, no build step: the browser loads the files as they are.

**`index.html`**: three sections: a search form, a results table, a downloads list. Loads `style.css` and `app.js` (with `defer`). Relative URLs (`app.js`, `api/search`) so it also works if the proxy serves Kinoarr under a sub-path.

**`app.js`**, split into small functions:
- `apiRequest(path, options)`: wraps `fetch`; on a non-2xx response throws an `Error` with the API's `detail` (or the HTTP status when there is none); on a network failure throws "Cannot reach Kinoarr".
- Search: `searchReleases(query)` → `renderResults(results)`. Shows "Searching…" while waiting, "No results" when empty. Renders the first `RESULTS_PAGE_SIZE = 50`; a "Show more" button renders the rest from the results already in memory (no new request).
- Download: `startDownload(releaseId, button)`: disables the button while the request runs, shows the outcome next to it, then calls `refreshDownloads()`.
- Downloads: `refreshDownloads()` calls `api/downloads?tag=kinoarr` and `renderDownloads(torrents)`. A `setInterval` with `DOWNLOADS_REFRESH_MS = 5000` calls it only when `document.hidden` is false; a `visibilitychange` listener refreshes immediately when the tab becomes visible again. An error replaces the list content with the message; the next successful refresh clears it.
- Subtitles: `fetchSubtitles(hash, button)` posts to `api/downloads/{hash}/subtitles` and shows the result: `downloaded` → "Subtitle saved: <file>", `already_present` → "Already has English subtitles", errors → the API's message. Button only shown when `progress >= 1`.
- Messages per row are stored by torrent hash, so the 5-second re-render does not wipe a subtitle result the user just got.
- Pure helpers: `formatSize(bytes)` (B/KB/MB/GB/TB, base 1024), `formatDate(iso)` (browser's locale), `describeState(state)` (maps qBittorrent states to "Downloading", "Finished", "Stalled", "Paused", "Queued", "Checking", "Error"; unknown states are shown as they are), `safeLink(url)` (returns the URL only if its protocol is `http:` or `https:`).
- **Safety**: elements are built with `document.createElement` and `textContent`; `innerHTML` is never used with data. Links get `rel="noopener noreferrer"` and `target="_blank"`. The torrent hash is URL-encoded in the subtitle request.

**`style.css`**: one small stylesheet, system font, colours as CSS variables with a `prefers-color-scheme: dark` override. On narrow screens the results table turns each row into a stacked card, so nothing scrolls sideways.

## Error handling
| Situation | What the user sees |
|---|---|
| Search fails (Prowlarr down, `502`) | The API's message in the results area |
| Download refused (`409`), unknown result (`404`) | The API's message next to the "Download" button |
| qBittorrent down (`502`) on refresh | Message in the downloads area; recovers on the next successful refresh |
| Subtitle not found (`404`), quota (`429`), disabled (`503`), other | The API's message next to that download |
| Kinoarr itself unreachable | "Cannot reach Kinoarr" |

## Testing strategy
- `tests/test_qbittorrent_client.py`: `list_torrents(tag="kinoarr")` passes `tag` to `torrents_info`; without `tag` it passes `None` (fake API extended with a `tag` argument).
- `tests/test_downloads.py`: `GET /api/downloads?tag=kinoarr` passes the tag to the client and returns only tagged torrents; combined with `completed=true`.
- New `tests/test_web_ui.py`: `GET /` returns `200` with `text/html` and the page's `<title>`; `GET /app.js` and `/style.css` return `200`; `/health` and `/api/...` still reach their routes (not shadowed by the mount); an unknown path returns `404`.
- JavaScript: no automated tests (would need Node tooling, a new dependency). Kept small, with pure helpers, and checked manually.

## Manual check (legal content only)
Run `uvicorn` against the dev compose and go through every acceptance criterion in `spec.md` in a browser, including phone width (responsive mode) and dark mode. **Only Internet Archive results are sent to qBittorrent.** For a finished torrent, use an Internet Archive download other than the trailer stuck at 98%. The HTML-in-title check uses a fake value injected through the browser console into `renderResults`, not a real indexer result.

## Risks / notes
- Polling every 5 seconds is one small qBittorrent request per open tab; it stops while the tab is hidden, so it is negligible on the home server.
- A result list left open across a Kinoarr restart gives `404` on "Download"; the message ("search again") explains it.
