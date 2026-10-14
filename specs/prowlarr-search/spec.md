# Spec: Prowlarr movie search

Status: Approved

## Goal
Let the user search for a movie by name and get a list of torrent releases found by Prowlarr, so they can later pick one to download.

## Context
Prowlarr is the indexer manager: it queries all configured indexers at once and returns their results through one API. Kinoarr is a client of Prowlarr; it does not manage indexers itself.

## User story
As a Kinoarr user, I type a movie name and see the matching torrent releases (title, size, seeders, indexer...), so I can choose the one I want.

## Requirements
1. `GET /api/search?query=<text>` returns a JSON list of search results.
2. Only movie results are requested (Torznab category 2000, "Movies").
3. Only torrent results are returned; Usenet results are dropped because qBittorrent cannot download them.
4. Each result includes: an opaque result ID, title, indexer name, size in bytes, seeders and leechers (if known), publish date, and info URL (if any).
5. Download links are never returned by the API: Prowlarr embeds its API key in them. Kinoarr keeps the links of recent search results in memory on the server, so a later download request only needs the result ID. Results with neither a download URL nor a magnet URL are dropped (there is nothing to download). A malformed result is skipped with a warning log; it does not fail the whole search.
6. Results are sorted by seeders, highest first; results with unknown seeders go last.
7. An empty or missing query is rejected with `422`.
8. If Prowlarr is unreachable, times out, rejects the API key, or returns invalid data, the API returns `502` with a clear message.
9. The Prowlarr API key is never logged, and never appears in any API response or error message.
10. Kinoarr restarting forgets stored results; the user then searches again.
11. Prowlarr's URL and API key come from `PROWLARR_URL` and `PROWLARR_API_KEY`; nothing is hardcoded.

## Acceptance criteria
- With a running Prowlarr and the Internet Archive indexer configured, `curl "localhost:8000/api/search?query=night+of+the+living+dead"` returns a non-empty list of torrent results.
- With Prowlarr stopped, the same request returns `502` with a message explaining Prowlarr cannot be reached.
- With a wrong API key, the request returns `502` with a message saying the API key was rejected.
- `GET /api/search?query=` returns `422`.
- No response from `/api/search` contains `apikey` or a Prowlarr download link.
- All unit tests pass without a running Prowlarr (HTTP is mocked).

## Known limitations
- Prowlarr answers `200` with an empty list when its indexers fail, so Kinoarr cannot tell "no results" from "indexers down" using the search response alone. Kinoarr returns the empty list as is.
- A search can take up to about 100 seconds, because Prowlarr waits for slow indexers.

## Out of scope
- Sending a result to qBittorrent (next implementation).
- Web UI (later step).
- Filtering by quality/resolution, pagination, caching.
- TV series.
- Using TMDb/IMDb IDs.

## Resolved questions
1. Sort order: by seeders, highest first (approved).
2. Incomplete results: tolerate missing seeders/leechers, drop results with no download link, skip malformed ones (approved).
3. Timeout: 120 seconds, as a constant (approved).
4. Download links: kept on the server, never sent to the browser; results are identified by an opaque ID (approved, option A).
