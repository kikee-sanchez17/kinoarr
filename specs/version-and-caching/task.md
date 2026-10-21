# Tasks: Show the version, and never serve an outdated page after an update

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. `/health` returns the version + test.
- [x] 2. `RevalidatedStaticFiles` with `Cache-Control: no-cache` + tests (200 and 304).
  - Checked against the running server too: `/app.js` → `200` with `cache-control: no-cache` and an `etag`; the same request with `If-None-Match` → `304 Not Modified`, also with `no-cache`. API answers carry no `cache-control`.
- [x] 3. Footer in `index.html`, `showVersion()` in `app.js`, `.page-footer` in `style.css` + test that the footer is in the page.
- [x] 4. Full test suite, ruff, `node --check`: all green.
  - 262 passed; ruff clean; `node --check` ok.

## Verification
- [x] 5. Headless Firefox screenshots at 1280px and 390px show "Kinoarr v0.2.0" in the footer.
  - "Kinoarr v0.2.0" at both widths; no sideways scroll at 390px. Fixed from the shot: the footer line was wider than the content (it covered the side padding); it now sits on the inner text and spans exactly the content width (56–1224px at 1280px).

## Review (before committing)
- [x] 6. Review the diff against `CLAUDE.md`.
- [x] 7. Explain the changes to the user and wait for approval.
- [x] 8. Commit only when the user says so.
