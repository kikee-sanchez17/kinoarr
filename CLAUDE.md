# Kinoarr — Project Context

## What it is
Kinoarr is a small self-hosted web app that searches for movies, downloads them through qBittorrent, checks whether the downloaded file has English subtitles, and fetches them if missing. It is an unofficial companion for Jellyfin. It will be published in a public GitHub repo under the MIT license, so it must work for other people's setups, not just mine.

## Pipeline
1. Search a movie via the Prowlarr API (Prowlarr is the indexer).
2. Send the chosen result to qBittorrent (Web API).
3. When the download finishes, detect existing subtitles with ffprobe (embedded and sidecar).
4. If no English subtitle exists, download one and save it as a `.srt` next to the movie file.
5. Jellyfin picks the files up on its own library scan; Kinoarr does not talk to Jellyfin in v1.

## Decisions (already made, do not revisit without asking)
- Backend: Python + FastAPI (chosen over Java for lower resource use on a small home server).
- Indexer: Prowlarr.
- Subtitles: English only; ignore forced and SDH tracks.
- Scope of v1: movies only (series later). Jellyfin integration is out of v1 (possible later extras: trigger a library refresh, mark movies already in the library via TMDb IDs).
- No authentication inside the app. In deployment the web UI is protected by an Nginx Proxy Manager access list. It is not exposed to the internet; it is reachable on the LAN and over Tailscale.
- License: MIT.
- README is written only once the project is finished (it will document both "everything in one compose" and "separate stacks" setups).

## Configuration rules
- Everything is configured through environment variables (see `.env.example`). Never hardcode container names, hosts, or paths.
- URLs: `QBITTORRENT_URL`, `PROWLARR_URL` (plus API keys where needed). Users may run everything in one compose file, or separate stacks, so the code must not assume either.
- **Path mapping** (important): qBittorrent reports file paths as it sees them (inside its container, or native Windows paths). Kinoarr may mount the same folder elsewhere. Use `map_path(path, remote_prefix, local_prefix)` (in `path_mapping.py`, still to be implemented) on every path coming from qBittorrent before ffprobe or the subtitle writer touches it. Variables:
  - `QBITTORRENT_DOWNLOADS_PATH` — the downloads folder as qBittorrent sees it (e.g. `/downloads`)
  - `KINOARR_DOWNLOADS_PATH` — the same folder as Kinoarr sees it
  - If either is empty, mapping is disabled and paths pass through unchanged.
- `map_path` normalizes backslashes, matches only on path boundaries (`/downloads` does not match `/downloads2`), and is case-insensitive only for Windows-style remote prefixes.
- Officially supported: Docker (Linux, and Windows via Docker Desktop). Native Windows should work but is untested. Write file operations with `pathlib`.
- The user running Kinoarr must be able to write to the downloads folder (to save subtitles); document `PUID`/`PGID` for Linux.

## Development environment
- Developed on a local PC with a Python virtualenv; the app runs outside Docker with `uvicorn`.
- `docker-compose.dev.yml` runs qBittorrent locally with a published port (use `http://localhost:<port>`). Prowlarr is to be added there (port 9696).
- Test with legal torrents only.
- Later it is deployed to a home server with Docker Compose. In production, each service lives in its own compose stack with its own network, plus a shared external network so Kinoarr can reach qBittorrent and Prowlarr by container name. Only the `.env` changes between dev and production, never the code.
- Nginx Proxy Manager (on a `proxy-net` network) exposes Kinoarr through a subdomain.

## Current status
Done (each feature has its spec in `specs/`):
- Project skeleton: FastAPI app with config, health endpoint, Dockerfile, compose file, `.env.example`, MIT LICENSE.
- qBittorrent client: `GET /api/downloads` and `/api/downloads/status`.
- Path mapping (`specs/path-mapping/`): `map_path` in `app/path_mapping.py`, applied to qBittorrent paths; `QBITTORRENT_DOWNLOADS_PATH` / `KINOARR_DOWNLOADS_PATH`.
- Prowlarr search (`specs/prowlarr-search/`): Prowlarr in `docker-compose.dev.yml`, `GET /api/search`. Download links stay server-side in an in-memory release store (they embed Prowlarr's API key); the API returns opaque result IDs.
- Send to qBittorrent (`specs/send-to-qbittorrent/`): `POST /api/downloads` with a result ID. Kinoarr opens the Prowlarr link itself and gives qBittorrent the `.torrent` file or magnet URI; torrents get the tag `kinoarr`; qBittorrent's default save folder is used.
- Subtitle detection (`specs/subtitle-detection/`): `GET /api/downloads/{hash}/subtitles` checks the torrent's largest video for English subtitles (embedded via ffprobe, sidecars `srt`/`ass`/`ssa`/`vtt` beside the video); forced, SDH and untagged do not count.
- Subtitle download (`specs/subtitle-download/`): OpenSubtitles (search by file hash, then by name), saved as `<video>.en.srt`; `POST /api/downloads/{hash}/subtitles` and a background checker every `POLL_INTERVAL` for finished `kinoarr` torrents (retry state in memory). Optional `OPENSUBTITLES_USERNAME`/`OPENSUBTITLES_PASSWORD` raise the daily quota (20/day on a free account).
- Tooling: ruff (format and lint, dev-only, configured in `pyproject.toml`).
- Web UI (`specs/web-ui/`, `specs/web-ui-improvements/`): static HTML/CSS/vanilla JS in `app/static/`, served by FastAPI at `/`. Search, downloads (polled, `kinoarr` tag via `GET /api/downloads?tag=`) and subtitles; results filtered in the browser by indexer, resolution and codec (`resolution`/`video_codec` detected from the title in `app/release_title.py`), 15 at a time with "Show more"; dark Jellyfin-like style. Untrusted text is rendered with `textContent` only.
- Deployment (`specs/deployment/`): allow-list `.dockerignore` (only `app/` and `requirements.txt` reach Docker); compose runs as `${PUID:-1000}:${PGID:-1000}` and names `ghcr.io/kikee-sanchez17/kinoarr:latest` next to `build: .`. `.github/workflows/publish-image.yml` publishes `X.Y.Z` and `latest` (amd64) only on `vX.Y.Z` tags, and fails if the tag differs from `APP_VERSION`. Values containing `$` go in single quotes in `.env` (Compose interpolates them otherwise).
- Subtitle matching (`specs/subtitle-matching/`): before OpenSubtitles, an English subtitle shipped inside the torrent folder (checked by its text, forced/SDH skipped) is copied beside the movie as `<video>.en.<ext>` (status `copied_from_torrent`; originals untouched for seeding). OpenSubtitles results are kept only if their movie title/year match the torrent or file name (a hash match once returned another movie). The checker runs without an API key too.
- Version and caching (`specs/version-and-caching/`): `/health` returns `version`; the UI footer shows it; page files are sent with `Cache-Control: no-cache`.

Release process: bump `APP_VERSION` in `app/config.py` in a "Release X.Y.Z" commit, push, then push the tag `vX.Y.Z`; on the server `git pull && docker compose pull && docker compose up -d`. Pushing needs the user's GitHub credentials (Claude cannot push from its session).

Production (home server, running v0.3.0): qBittorrent and Prowlarr each in their own stack on the external `media-net` network (containers `qbittorrent`, `prowlarr`); Kinoarr on `media-net` and `proxy-net`, behind Nginx Proxy Manager with an access list (LAN + Tailscale). Media mounted at `/downloads` in both qBittorrent and Kinoarr, so no path mapping; `PUID`/`PGID` 1000.

Dev Prowlarr indexers: Internet Archive (for development and tests; only its results are sent to qBittorrent when testing), plus The Pirate Bay and YTS (the user's real sources).

Next:
1. README (both setups, "everything in one compose" and "separate stacks"; ffprobe/ffmpeg for native installs, PUID/PGID, the OpenSubtitles variables, `$` in `.env` values, the release process and the published image).

Known open case (left on purpose): an English-tagged sidecar shipped by a torrent (`Movie.en.srt`) is trusted by name, even if it only contains an advertisement.

Dev note: the Internet Archive trailer in the dev qBittorrent is stuck at 98% (its `.ogv` stalls); use another Internet Archive download for end-to-end checks that need a finished torrent.

## Code quality (clean code)
- Write clean, readable, maintainable code. Favor clarity over cleverness.
- Use meaningful, intention-revealing names for variables, functions, classes and modules; avoid abbreviations and magic values (use named constants or settings).
- Keep functions small and focused on one thing; keep modules cohesive (single responsibility).
- Separate concerns: HTTP routes stay thin; business logic lives in services; external APIs (qBittorrent, Prowlarr, subtitle provider) live in their own client modules behind a clear interface, so they are easy to mock and replace.
- Avoid duplication (DRY), but do not over-abstract: no speculative generality or code for features that are not needed yet (YAGNI).
- Use type hints everywhere, and Pydantic models for request/response and configuration data.
- Handle errors explicitly: raise specific exceptions, never swallow them silently, and return clear HTTP errors from the API. Log useful context (never secrets or API keys).
- Prefer small pure functions that are easy to test; keep side effects (network, filesystem, subprocess calls) at the edges.
- Comments explain *why*, not *what*; if code needs a comment to explain what it does, consider renaming or restructuring it first.
- Follow PEP 8 and format/lint consistently (use the formatter and linter configured in the repo, such as ruff or black, if present).
- Every behavior change comes with tests; do not leave failing or skipped tests behind.

## Asking questions
- Ask clarifying questions whenever something is ambiguous, underspecified, or when there are several reasonable approaches with real trade-offs. Do not guess silently on things that affect design, behavior, or data.
- Ask before: changing a decision listed above, adding a new dependency, changing the public API shape, changing configuration variables, or doing anything destructive or hard to reverse (deleting files, rewriting history, overwriting data).
- Group questions and ask them up front, before writing a lot of code, offering a recommended option for each. For small, obvious details, pick the sensible default, state it, and continue.
- If a requirement conflicts with these conventions or with an earlier decision, point it out instead of working around it quietly.

## Workflow: Spec Driven Development
Every implementation gets its own folder `specs/<implementation-name>/` with three files, written before any code:
- `spec.md`: what and why (requirements, acceptance criteria, out of scope, open questions). No implementation details.
- `plan.md`: how (design, files, external APIs, error handling, testing strategy).
- `task.md`: ordered checklist of small tasks, ticked as they are done.

Steps:
1. Write spec, plan and tasks; wait for my approval before touching code.
2. Implement task by task, keeping `task.md` up to date.
3. Before committing, review the whole diff against every rule in this file (decisions, configuration, code quality, testing, language) and fix anything that does not comply.
4. Explain the changes to me and wait. Never commit without my explicit approval.

## Working conventions
- Keep changes small, with a clear commit message (committed only after my approval).
- Add unit tests for every new client or helper; mock HTTP calls in tests, and use the dev compose for manual integration checks.
- Keep dependencies minimal (the target server is low on RAM).
- Code, comments, commit messages and docs are in English. I talk to Claude in Spanish or English, so reply in the language I use.
- Explain concepts clearly when introducing something new; I am a junior-to-mid backend developer and like to understand why, not just copy code.
- Ask before changing any decision listed above.
