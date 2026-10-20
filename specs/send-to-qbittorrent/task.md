# Tasks: Send a search result to qBittorrent

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. Add `TorrentFile`, `MagnetLink`, `TorrentSource`, `DownloadRequest`, `DownloadStarted` to `app/models.py`.
- [x] 2. Add `fetch_torrent()` to `ProwlarrClient` + tests in `tests/test_prowlarr_client.py`.
- [x] 3. Factor the repeated qBittorrent error mapping into one helper (existing tests stay green).
- [x] 4. Add `add_torrent()` and `QBittorrentRejectedError` to `QBittorrentClient` + tests in `tests/test_qbittorrent_client.py`.
- [x] 5. Write `app/services/downloads.py` (`DownloadService`, `ReleaseNotFoundError`, `KINOARR_TAG`) + `tests/test_download_service.py`.
- [x] 6. Add `get_download_service()` to `app/dependencies.py`.
- [x] 7. Add `POST /api/downloads` to `app/api/downloads.py` + tests in `tests/test_downloads.py`.
- [x] 8. Run the full test suite: all green, none skipped (78 passed).

## Verification
- [x] 9. Manual check of every acceptance criterion in `spec.md` against the dev Prowlarr and qBittorrent, **using Internet Archive results only**. Confirm how the dev qBittorrent reports a duplicate (`"Fails."` or `409`) and that the `kinoarr` tag is created automatically.
  - Result: all criteria pass with an Internet Archive trailer. qBittorrent v5.2.4 (Web API 2.15.1) reports a duplicate as HTTP 409. The tag is created automatically. "qBittorrent stopped" simulated with a closed port. One Internet Archive item answered 401 (restricted) and Kinoarr returned 502, as designed.

## Review (before committing)
- [x] 10. Review the diff against `CLAUDE.md`:
  - Decisions respected (FastAPI, Prowlarr, movies only, no auth, no Jellyfin calls).
  - Configuration only through env vars; nothing hardcoded; no new variables.
  - Clean code: clear names, no magic values, small functions, type hints, Pydantic models.
  - Separation of concerns: thin route, Kinoarr rules in the service, external APIs in their clients.
  - Errors: specific exceptions, clear HTTP errors, API key never logged, returned, or sent outside Prowlarr.
  - No new dependencies.
  - Every behavior change has tests; nothing failing or skipped.
  - Code, comments and docs in English.
- [x] 11. Explain the changes to the user and wait for approval.
- [x] 12. Commit only when the user says so.
