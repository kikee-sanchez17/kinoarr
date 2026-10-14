"""Translate paths reported by qBittorrent into paths Kinoarr can open.

qBittorrent and Kinoarr often see the same downloads folder under different
paths (different container mounts, or a native Windows qBittorrent), so every
path coming from qBittorrent must go through `map_path` before Kinoarr touches
the filesystem.
"""

import re

POSIX_SEPARATOR = "/"
WINDOWS_SEPARATOR = "\\"

# "C:" style drive letters or "\\server\share" UNC paths.
_WINDOWS_PATH_PATTERN = re.compile(r"^([A-Za-z]:|\\\\)")


def map_path(path: str, remote_prefix: str, local_prefix: str) -> str:
    """Replace `remote_prefix` at the start of `path` with `local_prefix`.

    Returns `path` unchanged when mapping is disabled (either prefix empty)
    or when `path` is not inside `remote_prefix`.
    """
    if not remote_prefix or not local_prefix:
        return path

    normalized_path = _to_forward_slashes(path)
    normalized_remote = _strip_trailing_separator(_to_forward_slashes(remote_prefix))

    if not _is_inside(normalized_path, normalized_remote, ignore_case=is_windows_path(remote_prefix)):
        return path

    relative_part = normalized_path[len(normalized_remote) :]
    normalized_local = _strip_trailing_separator(_to_forward_slashes(local_prefix))
    return (normalized_local + relative_part) or POSIX_SEPARATOR


def is_windows_path(path: str) -> bool:
    return bool(_WINDOWS_PATH_PATTERN.match(path))


def _to_forward_slashes(path: str) -> str:
    return path.replace(WINDOWS_SEPARATOR, POSIX_SEPARATOR)


def _strip_trailing_separator(path: str) -> str:
    # The root "/" becomes "" so that "" + "/movies" rebuilds "/movies".
    return path.rstrip(POSIX_SEPARATOR)


def _is_inside(path: str, prefix: str, ignore_case: bool) -> bool:
    if ignore_case:
        path, prefix = path.casefold(), prefix.casefold()
    # Matching on a path boundary keeps "/downloads" from matching "/downloads2".
    return path == prefix or path.startswith(prefix + POSIX_SEPARATOR)
