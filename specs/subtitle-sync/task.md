# Tasks: Subtitles in sync with the movie

Implements [plan.md](plan.md). Tick each task when done.

## Implementation
- [x] 1. `app/release_title.py`: `detect_release_source`, `detect_release_group` + tests with the real Lady Bird release names.
- [x] 2. `app/models.py` + `app/clients/opensubtitles.py`: `release_name`, `frame_rate` on candidates; `synced_to_audio` on the fetch result + client tests.
- [x] 3. `app/clients/ffprobe.py`: `video_frame_rate` + tests.
- [x] 4. `app/clients/alass.py`: `AlassClient.sync`, `AlassError` + tests.
  - alass prints its errors on stdout (`error: ...`), not stderr, so the client looks for that line in both.
- [x] 5. `app/subtitles.py`: `DownloadDetails` and the new `best_candidate` ranking + tests, including the Lady Bird case.
  - A pre-release subtitle is not ranked down when the download itself is a pre-release copy.
- [x] 6. `SubtitleFetchService`: frame rate read, new ranking, re-timing of name matches, fallback without re-timing, temporary-file cleanup, `INFO` line + tests.
  - The OpenSubtitles part moved to `_download_from_opensubtitles` to keep `fetch()` short. alass writes `<video>.en.srt.synced.part`; its bytes then go through the usual atomic write. An empty alass output counts as a failure.
- [x] 7. `app/dependencies.py`: pass `FfprobeClient` and `AlassClient` to the fetch service.
  - `AlassClient` is always passed (not optional): a missing binary shows up as `AlassError` on use.
- [x] 8. API test for `synced_to_audio`; `app.js` message.
- [x] 9. `Dockerfile`: alass pinned by SHA-256; build the image and run `alass --version` inside it.
  - The legacy builder (used by a plain `docker build` here) silently ignores `ADD --checksum`, so the checksum is checked with `sha256sum` in a `RUN` step. A wrong checksum fails the build (tested).
- [x] 10. Full test suite and ruff: all green.
  - 332 passed; ruff check and format clean; `node --check app/static/app.js` ok.

## Verification
- [x] 11. Real OpenSubtitles name search for Lady Bird (no quota used): with a 23.976 fps BluRay YTS name, the chosen candidate is a 23.976 fps BluRay subtitle, not the screener.
  - 50 results, 17 for Lady Bird. Most downloaded: `Lady Bird 2017 DVDScr XVID AC3 HQ Hive-CM8` (30 fps). Chosen: `Lady.Bird.2017.720p.BluRay.x264.DTS-HDC` (23.976 fps, name match).
- [x] 12. Local check with an **Internet Archive** download: a subtitle shifted by 8 s comes back in sync. Note time and peak memory.
  - The dev trailer's `.en.srt` is for the full movie, so it can't be a reference. Used Internet Archive files fetched over HTTP instead (public domain, not through qBittorrent), with their `.asr.srt`, which Internet Archive generates from the file's own audio.
  - *House on Haunted Hill* (1959, 75 min, dialogue), through `AlassClient` with default options:
    - 8 s early → 0.19 s left (the untouched reference also measures 0.19 s, i.e. the ASR file's own offset). alass leaves an in-sync subtitle in sync.
    - subtitle from a 25 fps release on the 23.976 fps file, with or without +3 s → 0.19 s.
    - the reverse (×25/23.976) is not fixed: 48 s mean error. Added to the spec's known limitations.
    - 1.2 s per run, 71 MB peak memory (alass + ffmpeg). Same result inside the image as user 1000 (+7.81 s on all 452 lines, about 1 s).
  - *Park Conscious* (1938, 8 min, narration over constant music): alass moved even the untouched subtitle by about 8 s. Speech over continuous music defeats it. Also a known limitation.

## Review (before committing)
- [x] 13. Review the diff against `CLAUDE.md` (new dependency approved, API change limited to `synced_to_audio`, clean code, English, tests).
- [x] 14. Explain the changes to the user and wait for approval.
- [x] 15. Commit only when the user says so.

## After release (done by the user)
- [x] 16. Release a new version (bump `APP_VERSION`, tag), `docker compose pull && docker compose up -d` on the server.
  - 0.4.0 released and deployed by the user.
- [x] 17. Delete Lady Bird's `.en.srt`, press "Get subtitles": a BluRay subtitle, synced to the audio, first line on time in Jellyfin. Note time and memory from `docker stats kinoarr`.
  - With 0.4.0: `Lady.Bird.2017.720p.BluRay.x264.DTS-HDC` (23.976 fps, name match) was chosen instead of the screener, and the user confirmed it is in sync. It was saved without re-timing because of the bug in task 19, so the ranking alone fixed this movie. Re-timing on the server is still to be seen in a log after the fix is deployed.
- [ ] 18. README (later task): mention alass for native installs.

## Fix after 0.4.0
- [x] 19. On the server, alass refused the work file `….en.srt.unsynced.part` ("unknown subtitle format"): it picks the format from the extension. The subtitle was saved without re-timing (the ranking itself worked: `…720p.BluRay.x264.DTS-HDC`, 23.976 fps).
  - Work files now live in a temporary folder outside the media folder, named `unsynced.srt`/`synced.srt`.
  - New test: alass receives `.srt` work files outside the movie folder, and the folder is removed afterwards.
  - The earlier checks ran alass on `.srt` files directly and so missed it. Checked now through the real `SubtitleFetchService` with real ffprobe and alass, on the host and inside the image as user 1000: 8 s early → 0.19 s, only the `.en.srt` left in the movie folder.
