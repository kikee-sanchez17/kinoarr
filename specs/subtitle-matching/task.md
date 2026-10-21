# Tasks: Use the torrent's own subtitle, and never save another movie's subtitle

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. `app/subtitles.py`: `normalize_title`, `matches_movie` + tests (Emily Rose / Before I Fall / Exorcism of God cases).
- [x] 2. `app/subtitles.py`: `read_subtitle_text`, `looks_english` + tests with English, Spanish and French snippets.
  - Shares measured on the samples: English 0.55; Spanish 0.01, French 0.00, German 0.04, Italian 0.00 (threshold 0.25). German "was"/"will" and Italian "come" left out of the word list.
- [x] 3. `app/subtitles.py`: `bundled_subtitles`, `english_sidecar_path(extension=)` + tests.
- [x] 4. `app/models.py` + `app/clients/opensubtitles.py`: `movie_title`/`movie_year` from `feature_details`; new `copied_from_torrent` status + client tests.
- [x] 5. `SubtitleDetectionService.bundled_subtitles(hash)` + test.
- [x] 6. `SubtitleFetchService.fetch`: copy bundled English subtitle first; no-client check moved after it; filter OpenSubtitles results by movie, with INFO logs + tests.
  - Skipped results are logged once per search as one line listing each other movie, instead of one line per result (the real name search skipped 23). Titles are HTML-unescaped before matching (OpenSubtitles returns `Wallace &amp; Gromit`).
- [x] 7. Checker: always started; `SubtitleDownloadsDisabledError` → 24-hour retry + tests.
- [x] 8. API test for `copied_from_torrent`; `app.js` message.
- [x] 9. Full test suite and ruff: all green.
  - 256 passed; ruff check and format clean; `node --check app/static/app.js` ok.

## Verification
- [x] 10. Real OpenSubtitles search (no quota used) with hash `c333311f82a660b1` and the torrent name: the chosen candidate is *The Exorcism of Emily Rose*.
  - Hash search: 5 results, 4 kept, *Before I Fall (2017)* skipped → *The Exorcism of Emily Rose (2005)*, hash match. Name search: 37 results, 14 kept → *The Exorcism of Emily Rose (2005)*.
- [x] 11. Local end-to-end with an **Internet Archive** download that has a subtitle in its folder (or a test file added beside a finished one): "Get subtitles" answers "copied from the torrent".
  - On the finished Internet Archive trailer: its existing `.en.srt` moved aside, a test English `Subs/English.srt` added. `POST …/subtitles` → `copied_from_torrent`, copy byte-identical, original kept, log line written; a second call → `already_present`. Folder restored afterwards. Startup without `OPENSUBTITLES_API_KEY` logs the new message and starts the checker.

## Review (before committing)
- [x] 12. Review the diff against `CLAUDE.md` (no new dependencies, API change limited to the approved status, clean code, English, tests).
- [x] 13. Explain the changes to the user and wait for approval.
- [x] 14. Commit only when the user says so.

## After release (done by the user)
- [ ] 15. Release a new version (bump `APP_VERSION`, tag), `docker compose pull && docker compose up -d` on the server.
- [ ] 16. Delete the wrong `…YIFY.en.srt`, press "Get subtitles" on *The Exorcism of Emily Rose*: copied from the torrent, same text as the original `.srt`, English in Jellyfin.
