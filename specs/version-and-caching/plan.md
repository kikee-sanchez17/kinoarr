# Plan: Show the version, and never serve an outdated page after an update

Implements [spec.md](spec.md).

## Dependencies
None new.

## Design

### `app/main.py`
- `health()` returns `{"status": "ok", "version": APP_VERSION}`.
- New class `RevalidatedStaticFiles(StaticFiles)`, defined in `main.py` next to the mount, because it is only used there. It overrides `file_response(...)`: it calls `super()` and sets `Cache-Control: no-cache` on the response it gets back.
  - That covers both the full `200` answer and the `304 Not Modified` answer, because Starlette builds both in this one method (checked in Starlette 1.7.0).
  - `no-cache` does not mean "do not store". It means "store, but ask before reusing". Starlette already sends `ETag` and `Last-Modified`, so the browser's question is answered with a `304` when nothing changed.
- The mount uses `RevalidatedStaticFiles` instead of `StaticFiles`.

### `app/static/index.html`
After `</main>`:
```html
<footer class="page-footer"><span id="app-version">Kinoarr</span></footer>
```

### `app/static/app.js`
- `showVersion()` runs once at startup and calls `apiRequest("health")`.
  - On success it sets the footer text with `textContent` to `Kinoarr v${health.version}`.
  - On failure it leaves "Kinoarr" in place.
- `elements` gains `appVersion`.

### `app/static/style.css`
`.page-footer`:
- same max width and side padding as `main`;
- centered, `var(--text-muted)`, `0.8rem`;
- a top border in `var(--border)`, with padding above and below.

## Testing strategy
- `tests/test_web_ui.py`:
  - `/health` returns the status and `APP_VERSION`; this replaces the exact-equality assert.
  - `/`, `/app.js` and `/style.css` have `cache-control: no-cache`.
  - A second request with `If-None-Match` set to the first `ETag` returns `304`, also with `no-cache`.
  - The footer element is in the page.
- Headless Firefox screenshots at 1280px and 390px: the footer shows "Kinoarr v0.2.0".
- Full test suite, ruff, and `node --check`.
