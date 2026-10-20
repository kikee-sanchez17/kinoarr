# Tasks: Subtitle detection

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. Add `SubtitleStream`, `FoundSubtitle`, `SubtitleReport` to `app/models.py`.
- [x] 2. Write `app/subtitles.py` (pure rules) + `tests/test_subtitles.py`.
- [x] 3. Write `app/clients/ffprobe.py` (`FfprobeClient`, `FfprobeError`) + `tests/test_ffprobe_client.py`.
- [x] 4. Add `get_torrent()` to `QBittorrentClient` (shared `_to_torrent`) + tests.
- [x] 5. Write `app/services/subtitle_detection.py` + `tests/test_subtitle_detection_service.py`.
- [x] 6. Add `get_ffprobe_client()` and `get_subtitle_detection_service()` to `app/dependencies.py`.
- [x] 7. Add `GET /api/downloads/{torrent_hash}/subtitles` + route tests in `tests/test_downloads.py`.
- [x] 8. Run the full test suite: all green, none skipped (132 passed).

## Verification
- [x] 9. Manual check (see plan): trailer in `dev-media/` with and without sidecars; a generated `.mkv` with an English track. Clean up the test files afterwards.
  - Result: all cases behave as specified. The trailer is stuck at 98%, so through the API it gives 409. The sidecar cases were run on its folder with qBittorrent's answer faked as finished. The Arch ISO gives 422 and an unknown hash gives 404. A generated `.mkv` with `eng` and `eng` forced tracks reports only the non-forced one. Test files removed.

## Review (before committing)
- [x] 10. Review the diff against `CLAUDE.md`:
  - Decisions respected (English only, forced and SDH ignored, movies only, no Jellyfin calls).
  - Paths from qBittorrent go through `map_path`; file operations use `pathlib`.
  - Configuration only through env vars; nothing hardcoded; no new variables.
  - Clean code: clear names, named constants, small pure functions, type hints, Pydantic models.
  - Separation of concerns: thin route, rules in pure functions, subprocess and HTTP in their clients.
  - Errors: specific exceptions, clear HTTP errors, nothing secret logged.
  - No new dependencies.
  - Every behavior change has tests; nothing failing or skipped.
  - Code, comments and docs in English.
- [x] 11. Explain the changes to the user and wait for approval.
- [x] 12. Commit only when the user says so.
