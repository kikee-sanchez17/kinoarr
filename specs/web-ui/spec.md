# Spec: Simple web UI

Status: Approved

## Goal
Let the user search for a movie, start a download and follow its progress from a browser (desktop or phone), without calling the API by hand.

## Context
The backend pipeline is complete: `GET /api/search`, `POST /api/downloads`, `GET /api/downloads`, and `POST /api/downloads/{hash}/subtitles`, plus a background checker that fetches missing subtitles automatically. The UI is a thin layer on top of that API. There is no login: in deployment the page sits behind an Nginx Proxy Manager access list and is only reachable on the LAN and over Tailscale.

## User stories
- As a user, I type a movie title, see the matching releases with their size and seeders, and click one to start downloading it.
- As a user, I see Kinoarr's downloads with their progress, and the list updates while I keep the page open.
- As a user, when a download has finished I can ask for its English subtitle right away instead of waiting for the background checker.

## Requirements
1. Opening Kinoarr's root URL (`/`) shows the UI. `/health`, `/api/...` and `/docs` keep working as before.
2. **Search**
   - A search box with a button; submitting an empty query does nothing.
   - Results show: title, indexer, size (human-readable, e.g. "1.4 GB"), seeders, leechers, publish date, and a link to the release page when there is one. They keep the order the API returns (most seeders first).
   - Only the first 50 results are shown at first; a "Show more" button shows the rest. The API is unchanged.
   - While a search runs, the user sees that it is in progress; an empty result list says "No results".
3. **Download**
   - Each result has a "Download" button. Clicking it starts the download and tells the user whether it worked.
   - The API's error message is shown when it fails (e.g. "already in the list", "search again").
   - The downloads list refreshes right after a successful start.
4. **Downloads list**
   - Shows only torrents Kinoarr added (tag `kinoarr`), not the user's other torrents.
   - For each: name, progress (percentage and bar), state in plain words (e.g. "Downloading", "Finished", "Stalled", "Paused", "Error"), and size.
   - Refreshes automatically every 5 seconds while the page is visible; it does not poll while the browser tab is hidden.
5. **Subtitles**
   - Each finished download has a "Get subtitles" button. It fetches an English subtitle when one is missing, or reports that one already exists.
   - The result or error is shown next to that download (e.g. "Subtitle saved: Movie.en.srt", "Already has English subtitles", "No subtitle found", "Daily quota reached", "Subtitle downloads are disabled").
6. **API change**: `GET /api/downloads` accepts an optional `tag` query parameter that returns only torrents with that tag. Without it, the behaviour is unchanged.
7. **Safety**: text coming from indexers or qBittorrent (titles, names, URLs) is always shown as plain text, never interpreted as HTML. Release-page links are only shown when they use `http` or `https`.
8. **Errors**: when Kinoarr, Prowlarr or qBittorrent cannot be reached, the UI shows a clear message instead of failing silently or freezing.
9. Usable on a phone screen (no horizontal scrolling of the page) and readable in both light and dark browser themes.
10. No new configuration variables. No new runtime dependencies; the unused `jinja2` dependency is removed.

## Acceptance criteria
- `/` loads the UI in a browser from the dev setup (`uvicorn` + dev compose).
- Searching for an **Internet Archive** title lists results; a search with more than 50 results shows 50 and a working "Show more" button; clicking "Download" on an Internet Archive result shows success, and the torrent appears in the downloads list within a few seconds and its progress advances on its own.
- Downloading the same result again shows qBittorrent's "already in the list" message.
- Torrents added to qBittorrent by hand (without the `kinoarr` tag) do not appear in the list.
- "Get subtitles" on a finished Internet Archive download shows a result message (saved, already present, or not found).
- With qBittorrent stopped, the downloads list shows an error message, and it recovers on its own when qBittorrent is back.
- A release title containing HTML (e.g. `<b>x</b>`) is shown literally (covered by how the page builds its elements; checked manually with a crafted value).
- The page works at phone width in the browser's responsive mode.
- `GET /api/downloads?tag=kinoarr` returns only tagged torrents; all unit tests pass.

## Known limitations
- The background checker's own state (waiting for a retry, quota pause) is not shown; the user only sees what the "Get subtitles" button reports.
- Search results are kept in memory on the server: after a Kinoarr restart, a results list still open in the browser must be searched again before downloading (the UI shows the "search again" message).
- The page's JavaScript has no automated tests (there is no JavaScript tooling in the project); it is kept small and checked manually.

## Out of scope
- Pausing, removing or re-prioritising torrents.
- Showing whether a movie is already in Jellyfin.
- Choosing the save folder, category, or subtitle file manually.
- Authentication (handled by the proxy).
- Series.

## Resolved questions
1. Rendering: one static HTML page with plain JavaScript and CSS, served by FastAPI, calling the existing JSON API; no build step, no framework (approved).
2. Which downloads: only `kinoarr`-tagged ones, filtered by qBittorrent through a new optional `tag` parameter (approved).
3. Subtitles: a button per finished download using the existing endpoint; no new checker-status endpoint (approved).
4. Refresh: every 5 seconds while the page is open (approved).
5. JavaScript testing: manual only, no Node tooling (approved).
6. Long result lists: first 50, then "Show more", done in the browser (approved).
