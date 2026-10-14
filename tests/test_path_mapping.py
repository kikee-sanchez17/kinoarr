import pytest

from app.path_mapping import map_path


@pytest.mark.parametrize(
    ("path", "remote", "local", "expected"),
    [
        # POSIX to POSIX
        ("/downloads/movies/Sintel.mkv", "/downloads", "/data/media", "/data/media/movies/Sintel.mkv"),
        ("/downloads", "/downloads", "/data/media", "/data/media"),
        # Trailing slashes on either prefix are ignored
        ("/downloads/Sintel.mkv", "/downloads/", "/data/media/", "/data/media/Sintel.mkv"),
        # Root as a prefix
        ("/Sintel.mkv", "/", "/mnt/qbit", "/mnt/qbit/Sintel.mkv"),
        ("/downloads/Sintel.mkv", "/downloads", "/", "/Sintel.mkv"),
        ("/downloads", "/downloads", "/", "/"),
        # Windows qBittorrent (backslashes, drive letter) to a Linux mount
        (r"D:\Torrents\Movies\Sintel.mkv", r"D:\Torrents", "/downloads", "/downloads/Movies/Sintel.mkv"),
        (r"D:\Torrents\Sintel.mkv", "D:\\Torrents\\", "/downloads", "/downloads/Sintel.mkv"),
        ("D:/Torrents/Sintel.mkv", r"D:\Torrents", "/downloads", "/downloads/Sintel.mkv"),
        # Windows paths are case-insensitive
        (r"d:\torrents\Sintel.mkv", r"D:\Torrents", "/downloads", "/downloads/Sintel.mkv"),
        # UNC share
        (r"\\nas\media\Sintel.mkv", r"\\nas\media", "/downloads", "/downloads/Sintel.mkv"),
        # Native Windows Kinoarr: local prefix is a Windows path
        ("/downloads/Sintel.mkv", "/downloads", r"E:\Media", "E:/Media/Sintel.mkv"),
    ],
)
def test_maps_paths_inside_remote_prefix(path, remote, local, expected):
    assert map_path(path, remote, local) == expected


@pytest.mark.parametrize(
    ("path", "remote", "local"),
    [
        # Only whole path segments match
        ("/downloads2/Sintel.mkv", "/downloads", "/data/media"),
        (r"D:\Torrents2\Sintel.mkv", r"D:\Torrents", "/downloads"),
        # Outside the prefix entirely
        ("/other/Sintel.mkv", "/downloads", "/data/media"),
        # POSIX paths are case-sensitive
        ("/Downloads/Sintel.mkv", "/downloads", "/data/media"),
    ],
)
def test_leaves_paths_outside_remote_prefix_unchanged(path, remote, local):
    assert map_path(path, remote, local) == path


@pytest.mark.parametrize(
    ("remote", "local"),
    [("", "/data/media"), ("/downloads", ""), ("", "")],
)
def test_empty_prefix_disables_mapping(remote, local):
    path = r"D:\Torrents\Sintel.mkv"
    assert map_path(path, remote, local) == path
