# Tasks: Deployment to the home server

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. Add the allow-list `.dockerignore`.
- [x] 2. `docker-compose.yml`: `image: ghcr.io/kikee-sanchez17/kinoarr:latest` next to `build: .`, and `user: "${PUID:-1000}:${PGID:-1000}"`, with comments.
- [x] 3. `.env.example`: document `PUID`/`PGID`.
- [x] 4. `.github/workflows/publish-image.yml`: on `v*.*.*` tags, check the tag against `APP_VERSION`, then build `linux/amd64` and push `X.Y.Z` and `latest` to `ghcr.io` (current major versions of the Actions confirmed first).
  - Actions at their current majors (checked with `git ls-remote`): checkout v7, setup-buildx v4, login v4, metadata v6, build-push v7.

## Verification (local)
- [x] 5. Build the image: small build context, no `.env` or dev folders in it (throwaway listing build).
  - Context is 108.6 kB (was over 1.7 GB with `dev-media/`); the listing shows only `app/**` and `requirements.txt`, no `.env`, no `__pycache__`.
- [x] 6. `docker compose config` shows the right `user:` with and without `PUID`/`PGID`, and the `ghcr.io` image (temporary env file; only those lines printed).
  - `user: 1000:1000` without the variables, `1234:5678` with them; `image: ghcr.io/kikee-sanchez17/kinoarr:latest`. Found on the way: a `$` in a real `.env` value is read by Compose as a variable (warning `"ng" variable is not set`), so the container would get a wrong password. Single quotes keep it literal for both Compose and pydantic-settings (checked inside a container); documented at the top of `.env.example`.
- [x] 7. Run the image: `/`, `/health` and `/api/downloads` answer; the container becomes `healthy`.
  - Run with the real `.env` against the dev services: `healthy`; `/`, `/health` and `/api/downloads?tag=kinoarr` return 200. The checker's "path does not exist" log is expected (the dev `.env` maps paths to this PC, not the container).
- [x] 8. Permissions: writing into a mounted folder works as the owner's IDs and fails as another user.
  - As `1000:1000`: file created. As `4242:4242`: `Permission denied`. The `PUID/PGID` hint in the subtitle write error is covered by the existing unit tests.
- [x] 9. `actionlint` passes on the workflow; the version check accepts `v0.1.0` and rejects another tag when run locally.
  - `actionlint` 1.7.7 (Docker): no findings. Version check: `v0.1.0` accepted, `v0.2.0` rejected with the error message.
- [x] 10. Full test suite and ruff: all green.
  - 215 passed; ruff check and format clean.

## Review (before committing)
- [x] 11. Review the diff against `CLAUDE.md`: configuration only through `.env`, nothing secret in the build context or the workflow, least permissions, no new Python dependencies, English.
- [x] 12. Explain the changes to the user and wait for approval.
- [x] 13. Commit only when the user says so.

## Release (done by the user)
- [x] 14. Push the commit and the tag `v0.1.0`; the workflow publishes `0.1.0` and `latest`.
- [x] 15. Set the `kinoarr` package to public on GitHub; an anonymous `docker pull ghcr.io/kikee-sanchez17/kinoarr:0.1.0` works.

## On the home server (done by the user, legal content only)
- [ ] 16. External networks exist; qBittorrent is on `media-net` as `qbittorrent`; note its media mount path and `PUID`/`PGID` for `.env`.
- [ ] 17. Install Prowlarr in its own stack on `media-net` (container `prowlarr`, same `PUID`/`PGID`), add the indexers, copy its API key.
- [ ] 18. Clone the repo, write `.env` from `.env.example`, `docker compose pull && docker compose up -d`, container `healthy`.
- [ ] 19. Nginx Proxy Manager proxy host to `kinoarr:8000` with the access list; works from the LAN and over Tailscale, blocked elsewhere.
- [ ] 20. End-to-end with an **Internet Archive** release: search, download, progress, subtitle saved with `PUID:PGID` ownership, visible in Jellyfin after a scan.
