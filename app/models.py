from pydantic import BaseModel


class Torrent(BaseModel):
    """Vista simplificada de un torrent de qBittorrent."""

    hash: str
    name: str
    state: str
    progress: float  # 0.0 - 1.0
    size: int  # bytes
    save_path: str
    content_path: str
    category: str
    tags: list[str]