import qbittorrentapi

from app.models import Torrent
from app.path_mapping import map_path


class QBittorrentError(Exception):
    """No se pudo hablar con qBittorrent (conexión, login o error de API)."""


class QBittorrentClient:
    """Capa fina sobre qbittorrent-api: solo traduce llamadas, sin lógica de Kinoarr."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        remote_downloads_path: str = "",
        local_downloads_path: str = "",
    ) -> None:
        self._remote_downloads_path = remote_downloads_path
        self._local_downloads_path = local_downloads_path
        self._client = qbittorrentapi.Client(
            host=url,
            username=username,
            password=password,
            REQUESTS_ARGS={"timeout": (5, 15)},
        )

    def version(self) -> str:
        try:
            return self._client.app.version
        except qbittorrentapi.LoginFailed as exc:
            raise QBittorrentError("Login en qBittorrent fallido: revisa usuario y contraseña") from exc
        except qbittorrentapi.APIConnectionError as exc:
            raise QBittorrentError(f"No se puede conectar con qBittorrent: {exc}") from exc
        except qbittorrentapi.APIError as exc:
            raise QBittorrentError(f"Error de la API de qBittorrent: {exc}") from exc

    def list_torrents(self, completed_only: bool = False) -> list[Torrent]:
        try:
            raw = self._client.torrents_info(status_filter="completed" if completed_only else None)
        except qbittorrentapi.LoginFailed as exc:
            raise QBittorrentError("Login en qBittorrent fallido: revisa usuario y contraseña") from exc
        except qbittorrentapi.APIConnectionError as exc:
            raise QBittorrentError(f"No se puede conectar con qBittorrent: {exc}") from exc
        except qbittorrentapi.APIError as exc:
            raise QBittorrentError(f"Error de la API de qBittorrent: {exc}") from exc

        return [
            Torrent(
                hash=t.hash,
                name=t.name,
                state=t.state,
                progress=t.progress,
                size=t.size,
                save_path=self._to_local_path(t.save_path),
                content_path=self._to_local_path(getattr(t, "content_path", "")),
                category=t.category,
                tags=[tag.strip() for tag in t.tags.split(",") if tag.strip()],
            )
            for t in raw
        ]

    def _to_local_path(self, qbittorrent_path: str) -> str:
        return map_path(qbittorrent_path, self._remote_downloads_path, self._local_downloads_path)
