# Tasks: Simple web UI

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. Add the `tag` parameter to `QBittorrentClient.list_torrents()` + tests in `tests/test_qbittorrent_client.py`.
- [x] 2. Add `?tag=` to `GET /api/downloads` + tests in `tests/test_downloads.py`.
- [x] 3. Create `app/static/index.html` and `app/static/style.css` (layout, light/dark, narrow screens).
- [x] 4. Write `app/static/app.js`: `apiRequest`, pure helpers, search and results (first 50 + "Show more").
- [x] 5. Add "Download" to results in `app.js`.
- [x] 6. Add the downloads list with the 5-second refresh (paused while the tab is hidden) in `app.js`.
- [x] 7. Add "Get subtitles" per finished download in `app.js`, keeping messages across refreshes.
- [x] 8. Mount `app/static/` at `/` in `app/main.py` + `tests/test_web_ui.py`.
- [x] 9. Remove `jinja2` from `requirements.txt`; reinstall in a fresh virtualenv and run the tests to confirm nothing needed it.
- [x] 10. Run the full test suite: all green, none skipped.

## Verification
- [x] 11. Manual check of every acceptance criterion in `spec.md` in a browser against the dev compose, **using Internet Archive results only**, including phone width and dark mode.
  - Checked from the command line: `?tag=kinoarr` against the dev qBittorrent returns only the tagged trailer (the untagged ISO is left out); searches return 196 and 167 results, so "Show more" is exercised; all `info_url`s are http(s). Browser checks done by the user: everything works. Their screenshot showed short columns breaking mid-word ("The / Pirate / Bay", dates split); fixed by letting only titles wrap.
- [x] 12. Build the Docker image and confirm `/` serves the UI from the container.
  - Result: `/`, `/app.js`, `/style.css` and `/health` all return 200 from the container. Note: there is no `.dockerignore`, so the build context includes `dev-media/`, `dev-config/` and `.env` (not copied into the image, but slow); to fix in the deployment step.

## Review (before committing)
- [x] 13. Review the diff against `CLAUDE.md`:
  - Decisions respected (FastAPI, Prowlarr, movies only, no auth, no Jellyfin calls).
  - Configuration only through env vars; nothing hardcoded; no new variables.
  - Clean code: clear names, no magic values, small functions, type hints, Pydantic models.
  - Separation of concerns: thin routes, no Kinoarr rules in the clients.
  - Untrusted text never rendered as HTML; only `http(s)` links.
  - No new dependencies (one removed).
  - Every behavior change has tests; nothing failing or skipped.
  - Code, comments and docs in English.
- [x] 14. Explain the changes to the user and wait for approval.
- [x] 15. Commit only when the user says so.
