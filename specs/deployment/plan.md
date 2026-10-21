# Plan: Deployment to the home server

Implements [spec.md](spec.md).

## Dependencies
- No new Python dependencies.
- The workflow uses GitHub's and Docker's official Actions. These are reusable steps that GitHub downloads when the workflow runs; they are not installed in the project.
  - `actions/checkout`
  - `docker/setup-buildx-action`
  - `docker/login-action`
  - `docker/metadata-action`
  - `docker/build-push-action`
- Each one is pinned to its major version tag (for example `@v4`), so it gets bug fixes but no breaking changes. Before writing the workflow, check that these tags are the current majors.

## Design

### `.dockerignore` (new, at the repo root)
An allow-list: ignore everything, then let back in only what the `Dockerfile` copies. With a deny-list (listing `.env`, `dev-media/`...) any new secret or large file is sent unless someone remembers to add it. With an allow-list, a new file is excluded until the `Dockerfile` needs it.
```
# Send Docker only what the Dockerfile copies; everything else (.env, dev data, .git) stays out.
*
!app/
!requirements.txt
**/__pycache__
**/*.py[cod]
```
Rules are applied in order, and the last matching rule wins. That is why the `__pycache__` exclusions come after `!app/`. GitHub Actions builds from a fresh checkout, which has no `.env`, but the same rules apply there too.

### `.github/workflows/publish-image.yml` (new)
- **Trigger**: `on: push: tags: ["v*.*.*"]`. Branch pushes do nothing.
- **Permissions**: `contents: read` and `packages: write`, the least needed. It logs in to `ghcr.io` with the built-in `GITHUB_TOKEN`, so no secret has to be created by hand.
- **Steps**:
  1. Check out the code.
  2. Check the version. A shell step compares the tag without its `v` (`${GITHUB_REF_NAME#v}`) with the version read from `app/config.py` by `grep -Po '^APP_VERSION = "\K[^"]+'`. If they differ, the step prints both and exits with an error, and later steps don't run.
     - It uses `grep` rather than importing the module with Python. Importing `config.py` would need the app's dependencies (`pydantic_settings`) installed on the runner first.
  3. Set up Buildx, Docker's builder, which `build-push-action` needs.
  4. Log in to `ghcr.io` as `${{ github.actor }}` with `${{ secrets.GITHUB_TOKEN }}`.
  5. Run `docker/metadata-action` with `images: ghcr.io/${{ github.repository }}` and the tags `type=semver,pattern={{version}}` (the tag `v0.1.0` becomes `0.1.0`). For a semver tag the action adds `latest` on its own.
     - It also adds standard OCI labels, among them `org.opencontainers.image.source`. That label is what links the package to the repo on GitHub.
     - `github.repository` is the repo's name on GitHub, `kikee-sanchez17/kinoarr`, so a fork publishes to its own name with no edits. Docker requires lowercase names, and this one already is.
  6. Run `docker/build-push-action` with `platforms: linux/amd64`, `push: true`, and the tags and labels from step 5. A GitHub Actions layer cache (`cache-from`/`cache-to: type=gha`) means a rebuild with only Python changes doesn't reinstall ffmpeg.

### `docker-compose.yml`
```yaml
  kinoarr:
    image: ghcr.io/kikee-sanchez17/kinoarr:latest
    # Or build it yourself from a clone: docker compose up -d --build
    build: .
    ...
    # Must be able to write into the downloads folder to save subtitles:
    # usually the same IDs as the qBittorrent container.
    user: "${PUID:-1000}:${PGID:-1000}"
```
- With both `image:` and `build:`:
  - `docker compose pull` downloads the published image.
  - `docker compose up -d` uses it.
  - `docker compose up -d --build` builds locally and tags the result with that same name.
  - A later `docker compose pull` replaces a local build with the release.
- Compose reads `.env` from the project folder for `${...}` interpolation, the same way it already does for `${MEDIA_PATH}`. `:-1000` is the fallback when a variable is unset or empty.
- `env_file: .env` also passes `PUID`/`PGID` into the container. The settings ignore unknown variables (`extra="ignore"`), so this is harmless.
- Networks, volume, no published port and the healthcheck stay as they are.

### `.env.example`
A new block near the top:
```
# User and group that Kinoarr runs as (Docker on Linux). They must be able to write
# into MEDIA_PATH to save subtitles; usually the same PUID/PGID as qBittorrent.
# Find yours with: id -u / id -g
PUID=1000
PGID=1000
```

### Release procedure (by the user)
1. Make sure `APP_VERSION` in `app/config.py` is the version to release (it is `0.1.0` now).
2. `git tag v0.1.0 && git push origin v0.1.0`.
3. Watch the run in the repo's Actions tab.
4. After the first publish, open the package settings on GitHub and set its visibility to public.

### Server procedure (in `task.md`, done by the user)
1. **Networks**: make sure the external networks exist (`docker network create media-net`, and `proxy-net` if missing). Check that qBittorrent is on `media-net` with the container name `qbittorrent`, and note which path it mounts the media folder at and its `PUID`/`PGID`. These decide the `.env` values, including path mapping when the mount is not `/downloads`.
2. **Prowlarr**: run it in its own stack.
   - Image `lscr.io/linuxserver/prowlarr`, container name `prowlarr`, on `media-net`, with the same `PUID`/`PGID` and `TZ`.
   - Its web UI has to be reachable for setup: either publish `9696` on the LAN or add it to Nginx Proxy Manager with the access list.
   - Add the indexers (Internet Archive, The Pirate Bay, YTS) and copy its API key into Kinoarr's `.env`.
3. **Kinoarr**: `git clone` the repo, `cp .env.example .env`, and fill in the values. Then `docker compose pull && docker compose up -d`, and check `docker compose ps` for `healthy` and `docker compose logs kinoarr` for errors.
4. **Nginx Proxy Manager**: add a proxy host for the subdomain that forwards to `kinoarr` port `8000`, with the access list attached.
5. **Checks**: open it from the LAN and over Tailscale, then run the end-to-end check with an Internet Archive release.

## Error handling
No app code changes.
- A wrong `PUID`/`PGID` already produces the existing `500` subtitle error, which points at folder permissions.
- Wrong URLs or keys produce the existing `502` messages in the UI.
- A tag that doesn't match `APP_VERSION` fails the workflow with a message showing both values.
- A login or push failure fails the workflow, and nothing is published.

## Testing strategy
There are no unit tests, because no Python code changes. Local checks with Docker:
- **Build context**: build the image and read the size on the "transferring context" line. Then list the context with a throwaway build (`FROM busybox`, `COPY . /ctx`, `RUN find /ctx`) that uses the same `.dockerignore`, to confirm what is sent. The throwaway Dockerfile lives in the scratchpad and is passed with `-f`, so the repo's ignore rules still apply.
- **Interpolation**: run `docker compose config` with and without `PUID`/`PGID` set (in a temporary env file passed with `--env-file`, so the real `.env` is not edited or printed). Only the `user:` and `image:` lines are shown, never the whole output, because it contains the secrets from `.env`.
- **Run**: start the built image with a published port and check `/`, `/health` and `/api/downloads` (against the dev qBittorrent through the host). Wait for `healthy`.
- **Permissions**: mount a scratch folder owned by the current user. Writing into it succeeds with `--user $(id -u):$(id -g)` and fails with another user ID.
- **Workflow**: lint it with `actionlint`, run from its official Docker image (`rhysd/actionlint`, nothing installed in the project). Also run the version-check shell line locally against `app/config.py`, with a matching and a non-matching tag.
- **Real run**: only the user's tag push proves the whole workflow, because pushing a tag publishes to GitHub and is the user's call.
- The full pytest suite and ruff still pass. The changes don't touch Python, but this is the usual pre-commit check.
