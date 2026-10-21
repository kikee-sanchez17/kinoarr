# Spec: Show the version, and never serve an outdated page after an update

Status: Approved

## Goal
The user can see which Kinoarr version is running. After an update, the browser always uses the new page files.

## Context
After releasing 0.2.0, the UI said "Subtitle saved: …" for a subtitle that had been copied from the torrent. The 0.1.0 `app.js` shows that text for any status it does not know, including the new `copied_from_torrent`. The likely cause is that the browser kept the old `app.js`: Kinoarr's page files are sent without caching instructions, so browsers may reuse them for a while without asking. Nothing on the page tells which version is running, so this kind of mismatch is hard to spot.

## Requirements
1. **Version in the API**: `GET /health` returns `{"status": "ok", "version": "<APP_VERSION>"}`. This is useful from the command line and for monitoring too. `status` is unchanged.
2. **Version on the page**:
   - A muted footer at the bottom of the page shows "Kinoarr v0.2.0".
   - The page reads the version from `/health` once when it loads.
   - If that request fails, the footer shows just "Kinoarr", with no error message, because the downloads list already reports connection problems.
3. **No stale page files**:
   - The page files (`index.html`, `app.js`, `style.css`) are sent with `Cache-Control: no-cache`.
   - The browser keeps its copy but asks the server on every load whether it changed. The server answers "not modified" (an almost empty reply) when it did not, and sends the new file when it did.
   - API responses are not affected.
4. No new dependencies or configuration.

## Acceptance criteria
- Tests: `/health` includes the version from `APP_VERSION`; `/`, `/app.js` and `/style.css` carry `Cache-Control: no-cache`, also on a "not modified" (`304`) reply; the API routes still work.
- In the browser (headless Firefox screenshot and the user's own browser): the footer shows the running version, at desktop and phone width.
- After a release, a normal reload (no Ctrl+Shift+R) shows the new version in the footer.

## Out of scope
- Telling the user that a newer version exists on GitHub.
- Showing the version anywhere else (it is already in `/docs`).
