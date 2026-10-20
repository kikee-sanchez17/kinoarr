# Tasks: Subtitle download and background checker

Implements [plan.md](plan.md). Tick each task when done.

## Setup
- [x] 1. (User) Create an OpenSubtitles API key and put it in `.env` (optionally username/password). Then one real search and one real download to confirm the API field names; update the plan if they differ.

## Implementation
- [x] 2. Add `OPENSUBTITLES_USERNAME` / `OPENSUBTITLES_PASSWORD` to `app/config.py` and `.env.example`.
- [x] 3. Write `app/movie_hash.py` + `tests/test_movie_hash.py`.
- [x] 4. Add `SubtitleCandidate`, `SubtitleFetchResult` and `SubtitleReport.torrent_name` to `app/models.py`.
- [x] 5. Write `app/clients/opensubtitles.py` + `tests/test_opensubtitles_client.py`.
- [x] 6. Add `english_sidecar_path` and `best_candidate` to `app/subtitles.py` + tests.
- [x] 7. Write `app/services/subtitle_fetch.py` + `tests/test_subtitle_fetch_service.py`.
- [x] 8. Write `app/services/subtitle_checker.py` + `tests/test_subtitle_checker.py`.
- [x] 9. Add the dependency getters; start the checker in the `lifespan` of `app/main.py`.
- [x] 10. Add `POST /api/downloads/{torrent_hash}/subtitles` (shared error mapping with GET) + route tests.
- [x] 11. Run the full test suite: all green, none skipped (180 passed).

## Verification
- [x] 12. Manual check (see plan), Internet Archive downloads only, about 3 downloads of quota.
  - Result: through the API, no key → POST `503` and "checker is disabled" log; with key → checker starts, POST on the unfinished trailer → `409`. The trailer never finishes (its `.ogv` stalls at 97%), so fetch and checker were run with the real services on a scratch copy of its finished `.mp4`, with qBittorrent's answer faked as finished. Name-search fallback, download, `Trailer.en.srt` written, detection `true`, second fetch `already_present`, checker re-fetches once after the file is deleted, then leaves it alone. 3 downloads used in total (including task 1).

## Review (before committing)
- [x] 13. Review the diff against `CLAUDE.md`:
  - Decisions respected (English only, forced and SDH ignored, movies only, no Jellyfin calls).
  - Paths from qBittorrent go through `map_path`; file writes use `pathlib`.
  - Configuration only through env vars; new variables in `config.py` and `.env.example`.
  - Clean code: clear names, named constants, small pure functions, type hints, Pydantic models.
  - Separation of concerns: thin routes, rules in services/pure functions, OpenSubtitles in its own client.
  - Errors: specific exceptions, clear HTTP errors; API key, password and token never logged or returned.
  - No new dependencies.
  - Every behavior change has tests; nothing failing or skipped.
  - Code, comments and docs in English.
- [x] 14. Explain the changes to the user and wait for approval.
- [x] 15. Commit only when the user says so (include the CLAUDE.md status update).
