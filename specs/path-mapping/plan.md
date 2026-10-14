# Plan: Path mapping

Implements [spec.md](spec.md). Written retroactively.

## Dependencies
None new (standard library `re` only).

## Design

### `app/path_mapping.py`
A pure function: no filesystem, network or settings access, so it is trivial to test.

```python
def map_path(path: str, remote_prefix: str, local_prefix: str) -> str
```
1. Return `path` unchanged if either prefix is empty (mapping disabled).
2. Normalize `path` and both prefixes to forward slashes; strip trailing slashes from the prefixes. The root `/` becomes `""`, so `"" + "/movies"` rebuilds `/movies`.
3. Check the path is inside the remote prefix: equal to it, or starting with prefix + `/` (path boundary). Compare with `casefold()` only if the remote prefix is a Windows path (`is_windows_path`: matches `C:` or `\\`).
4. If outside, return `path` unchanged. Otherwise return local prefix + the rest of the path (or `/` if that is empty).

Output always uses forward slashes; Python on Windows accepts them, so no separate Windows branch is needed.

Strings are used rather than `pathlib`, because the remote path belongs to another machine/OS: `pathlib` would interpret it with the rules of the OS Kinoarr runs on.

### Settings (`app/config.py`, `.env.example`)
- Remove `downloads_path` / `DOWNLOADS_PATH`.
- Add `qbittorrent_downloads_path` and `kinoarr_downloads_path` (default `""`, i.e. disabled).
- `/api/config` shows the two new values.

### qBittorrent client (`app/clients/qbittorrent.py`)
- Constructor gains `remote_downloads_path` and `local_downloads_path` (default `""`).
- `save_path` and `content_path` go through `_to_local_path()` → `map_path()`.
- `app/dependencies.py` passes the two settings to the client, so the client never reads settings itself.

## Testing strategy
- `tests/test_path_mapping.py`: parametrized tables of input → expected output for mapped paths, unchanged paths, and disabled mapping.
- `tests/test_qbittorrent_client.py`: replace the library's inner client with a fake returning a Windows-path torrent; check the client returns mapped paths, and unchanged ones when mapping is disabled.
