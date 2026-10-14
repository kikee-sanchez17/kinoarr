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
Done:
- Project skeleton: FastAPI app with config, health endpoint, Dockerfile, compose file, `.env.example`, MIT LICENSE. First commit made.
- qBittorrent client: `/api/downloads` and `/api/downloads/status`, unit tests passing, verified against a local qBittorrent with a legal test torrent. Second commit made.

Next, in order:
1. Path mapping (not done yet): add `path_mapping.py` with `map_path(path, remote_prefix, local_prefix)` and unit tests (cover POSIX, Windows paths with backslashes and drive letters, path-boundary matching, trailing slashes, case rules, and empty config disabling the mapping). Then add the two path variables to settings and `.env.example`, and apply `map_path` in the qBittorrent client.
2. Add Prowlarr to `docker-compose.dev.yml`, configure a test indexer, write the Prowlarr client and the search endpoint with tests.
3. ffprobe-based subtitle detection (ffprobe must be in the Docker image and documented for native installs).
4. Subtitle download (provider still to be decided; OpenSubtitles is the likely candidate and needs an API key) and writing the `.srt` beside the movie.
5. Simple web UI: search box, results list, download status.
6. Deployment to the home server, then README.

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
