# Spec: Path mapping

Status: Done (written retroactively; implemented in commits `acefea5` and `426b62c`)

## Goal
Make the file paths reported by qBittorrent usable by Kinoarr, even when both programs see the downloads folder under different paths.

## Context
qBittorrent reports paths as it sees them: inside its container (e.g. `/downloads/Sintel.mkv`) or as native Windows paths (e.g. `D:\Torrents\Sintel.mkv`). Kinoarr may mount the same folder somewhere else (e.g. `/home/user/media/Sintel.mkv`). Without translation, ffprobe and the subtitle writer would look for files that do not exist from Kinoarr's point of view.

## User story
As someone running Kinoarr and qBittorrent in different containers, stacks, or operating systems, I set two variables once, and Kinoarr finds the downloaded files.

## Requirements
1. `map_path(path, remote_prefix, local_prefix)` replaces `remote_prefix` at the start of `path` with `local_prefix`.
2. Configured with `QBITTORRENT_DOWNLOADS_PATH` (folder as qBittorrent sees it) and `KINOARR_DOWNLOADS_PATH` (same folder as Kinoarr sees it).
3. If either variable is empty, mapping is disabled and paths pass through unchanged.
4. Backslashes are normalized to forward slashes.
5. Only whole path segments match: `/downloads` does not match `/downloads2`.
6. Matching is case-insensitive only when the remote prefix is a Windows path (drive letter or UNC share).
7. Trailing slashes on either prefix do not matter.
8. Paths outside the remote prefix are returned unchanged.
9. Every path coming from qBittorrent (`save_path`, `content_path`) is mapped in the qBittorrent client, before any other code uses it.
10. The old, unused `DOWNLOADS_PATH` variable is replaced by the two new ones.

## Acceptance criteria
- Unit tests cover POSIX paths, Windows paths with backslashes and drive letters, UNC shares, path-boundary matching, trailing slashes, the root prefix, case rules, and empty configuration.
- `/api/downloads` returns mapped paths when both variables are set.

## Out of scope
- Several mappings at once (one downloads folder is enough for v1).
- Checking that the mapped path exists (that is the job of the code that opens the file).
