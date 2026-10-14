from pydantic import BaseModel


class Torrent(BaseModel):
    """Simplified view of a qBittorrent torrent."""

    hash: str
    name: str
    state: str
    progress: float  # 0.0 - 1.0
    size: int  # bytes
    save_path: str
    content_path: str
    category: str
    tags: list[str]