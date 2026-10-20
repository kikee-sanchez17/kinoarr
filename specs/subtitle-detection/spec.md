# Spec: Subtitle detection

Status: Approved

## Goal
For a finished download, find out whether the movie already has an English subtitle that Jellyfin will show, so the next step only downloads subtitles when they are missing.

## Context
Subtitles can be **embedded** in the video file (a subtitle track inside the `.mkv`/`.mp4`) or a **sidecar**, a separate file next to the video (e.g. `Movie.en.srt`) that Jellyfin picks up by name. Kinoarr reads embedded tracks with `ffprobe` and sidecars by looking at the files in the folder. Paths come from qBittorrent and go through `map_path` first.

## User story
As a Kinoarr user, I can ask whether a finished download has an English subtitle, and see which ones were found.

## Requirements
1. `GET /api/downloads/{hash}/subtitles` returns, for that torrent: the video file that was checked (as Kinoarr sees it), whether an English subtitle is present, and the English subtitles found (embedded or sidecar, with a short description).
2. Works for any torrent in qBittorrent; the `kinoarr` tag only matters for the automatic checks in the next step.
3. **Which video**: the largest video file in the torrent (single-file torrent: that file; multi-file: the largest one under its folder). Samples, trailers and extras are ignored. Video extensions: `mkv`, `mp4`, `m4v`, `avi`, `mov`, `wmv`, `ts`, `webm`, `ogv`.
4. **Embedded English**: a subtitle track whose language tag is `eng` or `en` (any case). Image-based tracks (PGS, VobSub) count.
5. **Sidecar English**: a file in the same folder as the video, named `<video name>.<tags>.<ext>` with `ext` in `srt`, `ass`, `ssa`, `vtt` and a language tag `en` or `eng` among the tags (e.g. `Movie.en.srt`, `Movie.eng.ass`). Subfolders (e.g. `Subs/`) are not searched, because Jellyfin does not read them.
6. **Ignored**, per project decision:
   - forced tracks: disposition `forced`, or sidecar tag `forced`;
   - SDH tracks: disposition `hearing_impaired`, sidecar tags `sdh`, `hi` or `cc`, or an embedded track whose title contains "SDH" (many releases only mark it there).
   - untagged tracks and sidecars without a language tag (e.g. `Movie.srt`): the language is unknown, so they do not count.
7. Errors:
   - torrent not found → `404`;
   - torrent not finished downloading → `409`;
   - no video file in the torrent → `422`;
   - the path does not exist for Kinoarr (usually wrong path mapping) → `500` with a message pointing at `QBITTORRENT_DOWNLOADS_PATH` / `KINOARR_DOWNLOADS_PATH`;
   - `ffprobe` missing, failing or timing out → `500` with a clear message;
   - qBittorrent unreachable → `502`.
8. No new configuration variables. `ffprobe` is found on the `PATH`.

## Acceptance criteria
- For a finished test download with no subtitles, the endpoint returns `has_english_subtitle: false` and names the largest video file.
- After placing `<video>.en.srt` beside it, the endpoint returns `true` and lists that sidecar; `<video>.en.forced.srt` or `<video>.srt` alone keep it `false`.
- For an `.mkv` with an English subtitle track, it returns `true` and lists the track (test file generated with `ffmpeg` locally).
- An unknown hash returns `404`; a torrent still downloading returns `409`.
- All unit tests pass without qBittorrent or `ffprobe` installed (ffprobe output is faked from recorded JSON; the real `ffprobe` is exercised in the manual check).

## Out of scope
- Downloading subtitles, the background poller (next step).
- Languages other than English.
- Subtitles inside archives or subfolders.
- Detecting the language of untagged subtitles from their text.
- Documentation for native installs (goes in the README at the end).

## Resolved questions
1. Trigger: a detection service plus a read-only endpoint now; the background poller comes with subtitle downloading (approved).
2. Which file: the largest video file in the torrent (approved).
3. What counts: tagged English only; untagged is unknown; image-based tracks count (approved).
4. Sidecar formats: `srt`, `ass`, `ssa`, `vtt` (approved).
