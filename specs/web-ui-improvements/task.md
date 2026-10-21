# Tasks: Web UI improvements

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. `app/release_title.py` (`detect_resolution`, `detect_video_codec`) + `tests/test_release_title.py`.
- [x] 2. Add `resolution` and `video_codec` to `SearchResult`, fill them in `SearchService` + tests.
- [x] 3. Reorder `index.html` (search, downloads, results); add the brand span and the filter container.
- [x] 4. `app.js`: `setStatus` with kinds (info, busy, success, error); update all callers and subtitle messages.
- [x] 5. `app.js`: 15-per-page results with "Show more" adding 15 each time.
- [x] 6. `app.js`: provider, resolution and codec filters (`countValues`, `filteredResults`, `renderFilters`), combined, kept across searches when present. "Quality" column.
- [x] 7. `app.js`: fade-in only for new downloads (`knownDownloadHashes`).
- [x] 8. `style.css`: dark Jellyfin-like tokens, gradient header; check contrast.
- [x] 9. `style.css`: compact table, filter pills, hover/press/focus states, spinner, fade-in, reduced motion.
- [x] 10. Run the full test suite and ruff: all green.

## Verification
- [x] 11. Headless Firefox screenshots at 1280px and 390px.
  - Driven over WebDriver BiDi (scratch script, not part of the repo): search, provider/resolution/codec filters, "Show 15 more" (15 → 30 → 45 of 86, then hidden), "No results match these filters", filters kept on a second search, no horizontal scroll at 390px (page 378px wide). Fixed from the shots: count unreadable on the selected pill; "Title:" caption on phone cards; phone cards made shorter (details flow side by side). Note: headless Firefox does not advance animations between screenshots, so the script finishes them before each capture.
- [x] 12. User checks every acceptance criterion in the browser (Internet Archive results only for downloads).

## Review (before committing)
- [x] 13. Review the diff against `CLAUDE.md` (no external requests, no new dependencies, API change limited to the two new fields, untrusted text still only as text, English, clean code).
- [x] 14. Explain the changes to the user and wait for approval.
- [x] 15. Commit only when the user says so.
