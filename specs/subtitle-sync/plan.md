# Plan: Subtitles in sync with the movie

Implements [spec.md](spec.md).

## Dependencies
- **alass 2.0.0** (new, Docker image only): the static `alass-linux64` binary from the GitHub release, about 3 MB, installed as `/usr/local/bin/alass`. The download is pinned by SHA-256 (`7bd0b9ae7e035d3ba940eacffb21243614df36231d47f21f0b4ce42001ab7fcd`, checked on 2026-10-24). alass runs `ffmpeg` from the `PATH` to read the audio, and the image already has it.
- No new Python packages.

## Design

### Release names: `app/release_title.py`
Next to `detect_resolution` and `detect_video_codec`, with the same `_token` patterns and first-match rule:
- `ReleaseSource = Literal["pre-release", "BluRay", "WEB", "DVD", "HDTV"]`.
- `RELEASE_SOURCE_PATTERNS`, checked in this order:
  - pre-release first, since such a copy is timed differently even if its name mentions another source too: `cam|hdcam|camrip|ts|hdts|telesync|tc|hdtc|telecine|dvdscr|scr|screener|r5`;
  - `BluRay`: `blu-?ray|bdrip|brrip|bd|remux`;
  - `WEB`: `web`, `web-dl`, `webdl`, `web-rip`, `webrip`;
  - `DVD`: `dvd`, `dvdrip`, `dvd-rip`;
  - `HDTV`: `hdtv|pdtv`.
- `detect_release_source(title) -> ReleaseSource | None`.
- `detect_release_group(title) -> str | None`:
  - `YIFY` and `YTS` anywhere in the name (`[YTS.AM]`, `-YTS`, `.YIFY`) count as one group, `yts`, since YTS rarely puts its name after a dash;
  - otherwise the trailing `-GROUP` or `-[GROUP]`, lowercased. A name ending in `WEB-DL` has no group.

`TS` and `TC` are short, so the tests include names with `DTS` audio (`DTS-HDC`): `_token` already needs a non-letter before and after, so `DTS` does not count as `TS`.

### Models: `app/models.py`
- `SubtitleCandidate` gains `release_name: str | None` and `frame_rate: float | None` (`None` when the API gives `0` or nothing).
- `SubtitleFetchResult` gains `synced_to_audio: bool = False`.

### Clients
- `app/clients/opensubtitles.py`: `_to_candidate` fills `release_name` from `attributes["release"]` and `frame_rate` from `attributes["fps"]`.
- `app/clients/ffprobe.py`: new method `video_frame_rate(video_path) -> float | None`.
  - It runs `-select_streams v:0 -show_entries stream=r_frame_rate`, which today's `_run` gets as arguments (it now takes the stream selector and entries).
  - It parses `24000/1001`. `0/0`, an empty answer or no video stream gives `None`.
  - Errors stay `FfprobeError`, as today.
- `app/clients/alass.py` (new): `AlassClient(executable="alass")` with `sync(video_path, subtitle_path, output_path) -> None`.
  - It runs `alass <video> <subtitle> <output>` as an argument list (no shell), with `ALASS_TIMEOUT_SECONDS = 600`. Default options: they handle cuts and frame rate guessing.
  - A missing binary, a timeout or a non-zero exit raises `AlassError` with alass's `error:` line. alass prints errors on stdout, so both streams are searched.

### Ranking: `app/subtitles.py`
`best_candidate(candidates, download)` replaces today's version. `download` is a new small model `DownloadDetails(names: list[str], frame_rate: float | None)`, built by the fetch service from the torrent name, the video stem and ffprobe. The sort key, highest first:
1. `hash_match`;
2. `not is_pre_release`;
3. frame rate: match 2, unknown 1, mismatch 0, with `FRAME_RATE_TOLERANCE = 0.01`. When the video's rate is unknown, every candidate gets 1;
4. same source as the first name that has one;
5. same release group;
6. `download_count`.

These are small pure helpers, one per rule, so each is tested on its own.

### Fetch service: `app/services/subtitle_fetch.py`
The service gets two more collaborators: the `FfprobeClient` (for the frame rate) and an `AlassClient`. `dependencies.py` always passes one. A missing binary only shows up as `AlassError` on use, so native installs work without it.

In `fetch()`, after the torrent-copy step:
1. `_find_candidate` builds `DownloadDetails`. If ffprobe fails, it logs a warning and uses `frame_rate=None`.
2. Download the chosen file's bytes, as today.
3. If the candidate is a hash match, write the bytes with `_write_atomically`, as today.
4. Otherwise:
   - write the bytes to a temporary `<video>.en.srt.unsynced.part`;
   - run `alass.sync(video, that file, <video>.en.srt.synced.part)`;
   - read alass's output and write it with `_write_atomically`. An empty or missing output counts as an `AlassError`.

   On `AlassError`, log a warning ("… without re-timing it: …") and write the original bytes instead. The temporary files are always removed (`finally`).
5. Log one `INFO` line: `Saved subtitle X for torrent Y (name match, release 'Lady.Bird…BluRay…', 23.976 fps, video 23.976 fps, synced to the audio)`.
6. Return `synced_to_audio=True` only when alass succeeded.

`_write_atomically` already writes to a `.part` file and renames it, so the synced path only adds the alass step before it. The OpenSubtitles part of `fetch()` moves to `_download_from_opensubtitles`, to keep `fetch()` short.

The work still runs under the existing lock. The route is a plain `def`, so FastAPI runs it in a worker thread, and other requests aren't blocked while alass runs. The checker simply waits for the lock.

### API and UI
- `app/api/downloads.py`: no code change. The model carries the new field.
- `app/static/app.js`: in the subtitle message, `downloaded` with `synced_to_audio` → `Subtitle saved and synced to the audio: ${result.subtitle_file}`.

### Docker: `Dockerfile`
After the ffmpeg install, in the same layer style:
```dockerfile
# alass re-times downloaded subtitles to the movie's audio
ARG ALASS_URL=https://github.com/kaegi/alass/releases/download/v2.0.0/alass-linux64
ARG ALASS_SHA256=7bd0b9ae7e035d3ba940eacffb21243614df36231d47f21f0b4ce42001ab7fcd
ADD ${ALASS_URL} /usr/local/bin/alass
RUN echo "${ALASS_SHA256}  /usr/local/bin/alass" | sha256sum --check --quiet - \
    && chmod 0755 /usr/local/bin/alass
```
The `sha256sum` check makes the build fail if the file changes. `ADD --checksum` would be shorter, but the legacy builder silently ignores it. The `.dockerignore` allow-list isn't affected, since the file comes from the network.

## Error handling
| Situation | Result |
|---|---|
| ffprobe can't read the frame rate | Warning; ranking without the frame-rate rule |
| alass missing (native install) | Warning; subtitle saved without re-timing, `synced_to_audio: false` |
| alass fails or exceeds 10 minutes | Warning with alass's message; subtitle saved without re-timing |
| Temporary file can't be written | Existing `SubtitleWriteError` → `500` mentioning `PUID`/`PGID` |
| All results for other movies | Unchanged: `404` |

## Testing strategy
- `tests/test_release_title.py`: sources and groups for real names from the Lady Bird search (`DVDScr XVID AC3 HQ Hive-CM8` → pre-release; `720p.BluRay.x264.DTS-HDC` → BluRay, not pre-release; `WEB-DL.DD5.1.H264-FGT` → WEB, group `fgt`; `[YTS.AM]` and `YIFY` → `yts`); no source → `None`.
- `tests/test_subtitles.py`: each ranking rule on its own; the Lady Bird case with the real top results (release names, fps and download counts written into the test) picks `720p.BluRay.x264.DTS-HDC`; unknown video frame rate; a hash match still beats everything.
- `tests/test_opensubtitles_client.py`: `release` and `fps` mapped; `fps: 0` gives `None`.
- `tests/test_ffprobe_client.py`: `24000/1001`, `25/1`, `0/0`, no stream (fake subprocess, as today).
- `tests/test_alass_client.py` (new): the command line, a missing binary, a timeout, a non-zero exit (fake subprocess).
- `tests/test_subtitle_fetch_service.py` (fakes):
  - name match → alass called, synced output saved, `synced_to_audio: true`;
  - hash match → alass not called;
  - `AlassError` → original bytes saved, warning logged, `synced_to_audio: false`;
  - no temporary files left in any case;
  - the `INFO` line contains the match type, release and frame rates.
- `tests/test_downloads.py`: the response has `synced_to_audio`.
- Manual, local: the alass binary in the virtualenv's `PATH`. Take a finished **Internet Archive** download with speech and its `.en.srt`, shift the subtitle by 8 s with `ffmpeg -itsoffset`, and run the sync through the service. The result must be back in time. Note the time and peak memory (`/usr/bin/time -v`).
- Manual, home server (by the user, after the release): delete Lady Bird's `.en.srt`, press "Get subtitles", check the log line, the first line's timing in Jellyfin, and `docker stats kinoarr` during the run.
