# Spec: Send a search result to qBittorrent

Status: Approved

## Goal
Let the user pick one release from a search and have qBittorrent start downloading it, so the movie ends up in the downloads folder for the next pipeline steps (subtitles, Jellyfin).

## Context
`/api/search` returns releases identified by an opaque ID; their download links stay on the server because they embed Prowlarr's API key (see [prowlarr-search](../prowlarr-search/spec.md)). Those links point back at Prowlarr, which answers in one of two ways (observed against the dev Prowlarr):
- `200` with the `.torrent` file itself, or
- a redirect to a `magnet:` URI.

qBittorrent may not be able to reach Prowlarr (in dev `PROWLARR_URL` is `localhost`, which inside the qBittorrent container means qBittorrent itself), so Kinoarr opens the link and hands qBittorrent the result.

## User story
As a Kinoarr user, after searching I choose a release and Kinoarr starts downloading it in qBittorrent, marked so Kinoarr can find it again later.

## Requirements
1. `POST /api/downloads` with body `{"release_id": "<id>"}` starts the download of that release and returns `202 Accepted` with the release ID and title.
2. Only IDs from Kinoarr's own recent search results are accepted; the API never accepts a URL from the client.
3. Kinoarr opens the release's Prowlarr link itself:
   - a `.torrent` file is uploaded to qBittorrent;
   - a redirect to a `magnet:` URI is passed to qBittorrent as a magnet link;
   - a redirect to another `http(s)` URL is followed (some Prowlarr indexers redirect to the original site).
   When a release has both links, the `.torrent` link is used (qBittorrent can start right away instead of first fetching metadata from peers).
4. Every torrent Kinoarr adds gets the qBittorrent tag `kinoarr`, so later steps can tell Kinoarr's downloads apart from the user's other torrents.
5. Kinoarr does not choose a save folder: qBittorrent uses its own default.
6. Errors:
   - empty or missing `release_id` → `422`;
   - unknown ID (never searched, evicted, or Kinoarr restarted) → `404` with a message telling the user to search again;
   - Prowlarr or the indexer cannot provide the torrent (unreachable, timeout, HTTP error, unexpected answer) → `502`;
   - qBittorrent unreachable or login failed → `502`;
   - qBittorrent refuses the torrent (e.g. it is already in the list, or the file is invalid) → `409`.
7. The Prowlarr API key is never sent anywhere except Prowlarr, never logged, and never appears in a response or error message. In particular it is not sent to an indexer's site when following a redirect, and it is not given to qBittorrent.
8. No new configuration variables.

## Acceptance criteria
- After searching, `POST /api/downloads` with an **Internet Archive** result's ID returns `202`, and the torrent appears in qBittorrent with the tag `kinoarr` and starts downloading.
- Posting the same ID again returns `409`.
- Posting an unknown ID returns `404`; an empty one returns `422`.
- With qBittorrent stopped, the request returns `502`.
- No response or log line contains the Prowlarr API key.
- All unit tests pass without a running Prowlarr or qBittorrent.

## Known limitations
- Results are kept in memory only: after a Kinoarr restart the user must search again before downloading.
- Kinoarr does not check whether the movie already exists in the downloads folder or in Jellyfin.

## Out of scope
- Choosing the save folder or a qBittorrent category.
- Detecting the download finishing (next steps: poller, subtitles).
- Web UI.
- Removing or pausing torrents.

## Resolved questions
1. Handoff: Kinoarr resolves the Prowlarr link and gives qBittorrent the `.torrent` bytes or the magnet URI (approved).
2. Marking: fixed tag `kinoarr`, constant in code (approved).
3. Save path: qBittorrent's default, no new variable (approved).
4. API shape: `POST /api/downloads` with `{"release_id": ...}`, `202` on success (approved).
