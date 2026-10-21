# Spec: Deployment to the home server

Status: Approved

## Goal
Run Kinoarr on the home server with Docker Compose, in its own stack, reachable through Nginx Proxy Manager on the LAN and over Tailscale. The server pulls a prebuilt image from GitHub instead of building it. Building the image must be safe (no secrets sent to Docker), and Kinoarr must be able to write subtitles into the downloads folder.

## Context
The app is feature-complete for v1, and a `Dockerfile` and `docker-compose.yml` already exist. Three things are missing:
- **No `.dockerignore`.** `docker build` sends the whole folder to Docker as the "build context", including `.env` (with real API keys and passwords), `dev-config/` and `dev-media/`. The `Dockerfile` only copies `app/` and `requirements.txt`, so these files do not end up in the image. Still, they are sent on every build, which is slow, and a future `COPY . .` would leak them.
- **The container user is hardcoded** (`user: "1000:1000"`). On Linux, Kinoarr needs to write `.srt` files next to qBittorrent's downloads. That only works when it runs as a user that owns, or can write to, that folder. `1000:1000` is right on many machines but not all, and this is a public repo.
- **No published image.** Today the image can only be built from a clone. The home server is low on resources (AMD A6-6310, amd64), and other users of the public repo should be able to pull a ready image.

In production each service lives in its own compose stack. `proxy-net` is shared with Nginx Proxy Manager. `media-net` is shared with qBittorrent and Prowlarr, so Kinoarr reaches them by container name (`http://qbittorrent:8081`, `http://prowlarr:9696`). qBittorrent already runs on the server; Prowlarr does not yet. Only `.env` differs between dev and production.

## User stories
- As the server owner, I release a version by pushing a git tag. GitHub builds and publishes the image, and the server picks it up with `docker compose pull && docker compose up -d`.
- As the server owner, I open Kinoarr through its subdomain from my LAN or over Tailscale. Nobody else can reach it.
- As a user of the public repo, I pull the published image and set my own user and group IDs in `.env` instead of editing the compose file.

## Requirements
1. **Build context**: a `.dockerignore` lets only what the image needs reach Docker: `app/` and `requirements.txt`, without `__pycache__` or compiled Python files. `.env`, `.git`, `.venv`, `dev-config/`, `dev-media/`, `tests/` and `specs/` are never sent.
2. **Container user**: `docker-compose.yml` runs Kinoarr as `PUID:PGID` from `.env`. It falls back to `1000:1000` when they are not set, so existing setups keep working. `.env.example` documents both and explains how to find the right values (`id` on Linux, matching the qBittorrent container's `PUID`/`PGID`). Only Docker Compose reads them; the app does not.
3. **Published image**:
   - Pushing a git tag of the form `vX.Y.Z` (for example `v0.1.0`) makes GitHub Actions build the image and publish it to `ghcr.io/kikee-sanchez17/kinoarr` with the tags `X.Y.Z` and `latest`.
   - Pushes to `main` publish nothing, so the server only changes when a version is released on purpose.
   - The image is built for `linux/amd64`.
   - The publish fails, and nothing is published, when the tag does not match the app's version (`APP_VERSION`, shown in `/docs` and sent to OpenSubtitles in the user agent), so the image tag and the version the app reports always agree.
   - The image is linked to the GitHub repo, so the package page points at the source.
4. **Compose image**: `docker-compose.yml` names the published image (`ghcr.io/kikee-sanchez17/kinoarr:latest`) and keeps `build: .`. `docker compose pull` fetches the release; `docker compose up -d --build` still builds locally from a clone.
5. **Networks and access**: unchanged. Kinoarr joins the external `proxy-net` and `media-net` networks (fixed names) and publishes no port in production.
6. **Health**: the existing `/health` healthcheck in the image keeps working, and `docker compose ps` shows the container as `healthy`.
7. **Updating**: on the server, `git pull` (for compose and `.env.example` changes), then `docker compose pull && docker compose up -d`.
8. No change to the app code, its API, or its runtime dependencies.

## Acceptance criteria
Locally (dev PC):
- `docker build` sends only a few hundred kB of build context (not the size of `dev-media/`), and a file listing of the context shows no `.env`.
- `docker compose config` shows `user: "1000:1000"` without `PUID`/`PGID` in `.env` and the given values when they are set, plus the `ghcr.io` image name.
- The image starts, `/`, `/health` and `/api/...` answer, and the container becomes `healthy`.
- Running as `PUID:PGID`, the container can create a file in a mounted downloads folder owned by that user. Running as another user, writing fails, and Kinoarr's subtitle error message points at `PUID`/`PGID`.
- The workflow file passes a GitHub Actions linter.

On GitHub and the home server (done by the user, legal content only):
- Pushing the tag `v0.1.0` runs the workflow, which publishes `ghcr.io/kikee-sanchez17/kinoarr:0.1.0` and `:latest`. The package is set to public, and anonymous `docker pull` works.
- A test tag that does not match `APP_VERSION` makes the workflow fail without publishing. Deleting that test tag afterwards is optional.
- Prowlarr runs in its own stack on `media-net` with its indexers configured.
- `docker compose pull && docker compose up -d` starts Kinoarr from the published image, and the container becomes `healthy`.
- The web UI loads through the Nginx Proxy Manager subdomain from the LAN and over Tailscale, and the access list blocks other clients.
- A search returns results from Prowlarr. An **Internet Archive** download goes to qBittorrent and shows progress in the UI.
- After it finishes, "Get subtitles" (or the background checker) saves the `.srt` next to the movie, owned by `PUID:PGID`, and Jellyfin shows it after a library scan.

## Known limitations
- Dependencies in `requirements.txt` are minimum versions (`>=`), so a new release may install newer libraries than the ones tested. A lock file could fix that later, but it changes how dependencies are managed, so it is not part of this step.
- The image includes the whole `ffmpeg` package (about 300 MB on disk; it does not affect RAM) only to get `ffprobe`.
- Search results and subtitle retry state stay in memory and are lost on a container restart, as before.
- Releasing means bumping `APP_VERSION` in `app/config.py` first, then pushing the matching tag.
- GitHub makes a newly published package private. It has to be switched to public once, by hand, in the package settings.

## Out of scope
- Images for ARM (`arm64`) or other architectures.
- Running tests or ruff in CI (the workflow only publishes images).
- Making the network names configurable.
- Setting up qBittorrent, Nginx Proxy Manager or Tailscale; they already run on the server. Installing Prowlarr is part of the server checklist, but its compose file is not added to the repo.
- The README with both setups ("everything in one compose" and "separate stacks"). It is the next step.

## Resolved questions
1. New variables `PUID`/`PGID`, read by Compose only, with a fallback to `1000` (approved).
2. The server pulls a prebuilt image from GitHub Container Registry, published only for version tags (approved).
3. Architecture: `linux/amd64` only (the server runs an AMD A6-6310).
4. Compose keeps both `image:` and `build: .` (approved).
5. Network names stay fixed and are documented in the README (approved).
6. Prowlarr is installed on the server through steps in `task.md`; no Prowlarr compose file in the repo (approved).
