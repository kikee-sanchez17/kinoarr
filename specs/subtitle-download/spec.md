# Spec: Subtitle download and background checker

Status: Approved

## Goal
When a Kinoarr download finishes and has no English subtitle, fetch one from OpenSubtitles and save it as `.srt` next to the movie, automatically, so Jellyfin shows English subtitles without the user doing anything.

## Context
[subtitle-detection](../subtitle-detection/spec.md) already tells whether a finished download has an English subtitle. OpenSubtitles (opensubtitles.com REST API) provides subtitles: searching is free; downloads need an API key and are limited per day (about 5 without login, about 10–20 with a free account; these figures come from community sources, to confirm against the real API).

## User stories
- As a Kinoarr user, a movie I downloaded through Kinoarr gets an English subtitle on its own a few minutes after it finishes.
- As a Kinoarr user, I can ask Kinoarr to fetch the subtitle for one download right now.

## Requirements

### Fetching one subtitle
1. `POST /api/downloads/{hash}/subtitles` fetches an English subtitle for that download if it has none, and returns what happened: `downloaded` (with the saved file name) or `already_present`.
2. **Matching**: first search by the movie file's OpenSubtitles hash (an exact match with this release, so the timing fits); if that finds nothing, search by the torrent name. Hash matches are preferred, then the most downloaded subtitle.
3. Forced and SDH subtitles are never chosen (project decision). Subtitles split over several files (CD1/CD2) are skipped.
4. The file is saved beside the movie as `<video name>.en.srt`, which the detection step and Jellyfin both recognise. It is written to a temporary file first and then renamed, so Jellyfin never sees a half-written subtitle.
5. Errors:
   - torrent not found `404`, not finished `409`, no video `422`, path missing `500` (same as detection);
   - no English subtitle on OpenSubtitles → `404` with a message saying so;
   - daily download quota used up → `429` with the reset time when OpenSubtitles gives one;
   - OpenSubtitles unreachable, timeout, rejected API key or login, unexpected answer → `502`;
   - subtitle downloads not configured (no API key) → `503`;
   - cannot write the file → `500` with a message pointing at folder permissions (`PUID`/`PGID`).
6. Only one subtitle download runs at a time (the manual endpoint and the checker share it), so the same movie is not fetched twice.

### Background checker
7. When Kinoarr starts and an API key is configured, a background checker runs every `POLL_INTERVAL` seconds. Without an API key it does not start, and Kinoarr logs that once.
8. Each round it looks at finished torrents with the `kinoarr` tag and fetches a subtitle for those without an English one.
9. Retries, kept in memory:
   - no subtitle found → that torrent is retried after 24 hours;
   - quota used up → no downloads until the reset time OpenSubtitles reports (24 hours if it reports none);
   - any other error (OpenSubtitles or qBittorrent down, ffprobe failure...) → logged, retried next round;
   - a torrent that has an English subtitle is not checked again (until Kinoarr restarts).
   After a restart everything is retried once, which is acceptable.
10. One failing torrent never stops the round for the others, and an error never stops the checker.

### Configuration
11. `OPENSUBTITLES_API_KEY` (existing) is required for downloads. New optional `OPENSUBTITLES_USERNAME` and `OPENSUBTITLES_PASSWORD`: when both are set, Kinoarr logs in for the higher quota; otherwise it downloads anonymously.
12. The API key, password and login token are never logged or returned.

## Acceptance criteria
- With an API key set, `POST /api/downloads/{hash}/subtitles` on a finished Internet Archive download without subtitles returns `downloaded`, and `<video>.en.srt` appears beside the video; `GET .../subtitles` then reports `true`.
- Calling it again returns `already_present` and does not use quota.
- With no API key the POST returns `503`, and the log says the checker is disabled.
- With the checker running, a finished `kinoarr` download without subtitles gets its `.srt` within one `POLL_INTERVAL`, and the next rounds leave it alone.
- Unit tests pass without network, qBittorrent or ffprobe.
- Manual tests are frugal with the daily quota (a handful of downloads).

## Known limitations
- Retry state is in memory; a restart retries everything once.
- Wrongly tagged or unsynced subtitles from OpenSubtitles are possible; the user can delete the `.srt`, and Kinoarr will fetch another (possibly the same) on the next round.
- The existing `SUBTITLE_LANGUAGES` setting stays unused: English only is a project decision. Removing it is a separate config change to decide later.

## Out of scope
- Other languages, other providers.
- Choosing among several subtitles in the UI.
- Persisting retry state; telling Jellyfin to rescan.
- Series.

## Resolved questions
1. Provider: OpenSubtitles (approved).
2. Login: optional `OPENSUBTITLES_USERNAME` / `OPENSUBTITLES_PASSWORD` (approved).
3. Matching: file hash first, then release name (approved).
4. Retries: in memory; 24 h after "not found", pause until quota reset (approved).
5. Manual trigger: `POST /api/downloads/{hash}/subtitles` (approved).
6. Background checker in this step (approved).
