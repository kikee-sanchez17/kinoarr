from datetime import datetime
from typing import Any

import httpx

from app.models import SubtitleCandidate

API_BASE_URL = "https://api.opensubtitles.com/api/v1"
REQUEST_TIMEOUT_SECONDS = 30
ENGLISH = "en"
SUBTITLE_FORMAT = "srt"
# The API wants these exact values; anything else makes it answer with a redirect.
SEARCH_FILTERS = {
    "foreign_parts_only": "exclude",
    "hearing_impaired": "exclude",
    "languages": ENGLISH,
    "type": "movie",
}
# Flags on a search result that disqualify it, even if the filters above should have dropped it already.
EXCLUDED_FLAGS = ("hearing_impaired", "foreign_parts_only", "ai_translated", "machine_translated")


class OpenSubtitlesError(Exception):
    """Could not talk to OpenSubtitles (connection, credentials, HTTP or response error)."""


class QuotaExceededError(OpenSubtitlesError):
    """The daily download quota is used up."""

    def __init__(self, reset_at: datetime | None) -> None:
        when = f"; it resets at {reset_at:%Y-%m-%d %H:%M} UTC" if reset_at else ""
        super().__init__(f"OpenSubtitles daily download quota used up{when}")
        self.reset_at = reset_at


class OpenSubtitlesClient:
    """Thin wrapper over the OpenSubtitles REST API: translates calls, holds no Kinoarr logic."""

    def __init__(self, api_key: str, username: str, password: str, user_agent: str) -> None:
        self._username = username
        self._password = password
        self._token: str | None = None
        # The API blocks generic user agents, so Kinoarr names itself.
        self._client = httpx.Client(
            base_url=API_BASE_URL,
            headers={"Api-Key": api_key, "User-Agent": user_agent},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    def search_english(self, movie_hash: str | None = None, query: str | None = None) -> list[SubtitleCandidate]:
        """Search by file hash or by name; returns usable single-file English subtitles."""
        params = dict(SEARCH_FILTERS)
        if movie_hash:
            params["moviehash"] = movie_hash
        if query:
            params["query"] = query.lower()
        response = self._send("GET", "/subtitles", params=dict(sorted(params.items())))
        try:
            results = response.json()["data"]
            return [_to_candidate(result["attributes"]) for result in results if _is_usable(result["attributes"])]
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise OpenSubtitlesError("Unexpected search response from OpenSubtitles") from exc

    def download(self, file_id: int) -> bytes:
        response = self._send("POST", "/download", json={"file_id": file_id, "sub_format": SUBTITLE_FORMAT})
        try:
            link = response.json()["link"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OpenSubtitlesError("Unexpected download response from OpenSubtitles") from exc
        # The link is a plain file URL on another host: no API key or token needed.
        return self._fetch_file(link)

    @property
    def _has_login(self) -> bool:
        return bool(self._username and self._password)

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._has_login and self._token is None:
            self._login()
        response = self._request(method, path, **kwargs)
        if response.status_code == httpx.codes.UNAUTHORIZED and self._has_login:
            # Tokens expire; log in again once before giving up.
            self._login()
            response = self._request(method, path, **kwargs)
        _raise_for_status(response)
        return response

    def _login(self) -> None:
        self._token = None
        response = self._request("POST", "/login", json={"username": self._username, "password": self._password})
        _raise_for_status(response)
        try:
            body = response.json()
            self._token = body["token"]
            base_url = body.get("base_url")
        except (ValueError, KeyError, TypeError) as exc:
            raise OpenSubtitlesError("Unexpected login response from OpenSubtitles") from exc
        # Some accounts are told to use another API host.
        if base_url:
            self._client.base_url = f"https://{base_url}/api/v1"

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            return self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise OpenSubtitlesError("OpenSubtitles timed out") from exc
        except httpx.TransportError as exc:
            raise OpenSubtitlesError("Cannot connect to OpenSubtitles") from exc

    def _fetch_file(self, link: str) -> bytes:
        try:
            response = httpx.get(link, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
        except httpx.TimeoutException as exc:
            raise OpenSubtitlesError("Timed out while downloading the subtitle file") from exc
        except httpx.TransportError as exc:
            raise OpenSubtitlesError("Cannot connect to OpenSubtitles to download the subtitle file") from exc
        if response.status_code != httpx.codes.OK or not response.content:
            raise OpenSubtitlesError(f"Could not download the subtitle file: HTTP {response.status_code}")
        return response.content


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
        raise OpenSubtitlesError(
            "OpenSubtitles rejected the credentials: check OPENSUBTITLES_API_KEY, "
            "OPENSUBTITLES_USERNAME and OPENSUBTITLES_PASSWORD"
        )
    if status == httpx.codes.NOT_ACCEPTABLE:
        raise QuotaExceededError(_reset_time(response))
    if status == httpx.codes.TOO_MANY_REQUESTS:
        raise OpenSubtitlesError("OpenSubtitles rate limit reached: try again shortly")
    if response.is_error:
        raise OpenSubtitlesError(f"OpenSubtitles returned HTTP {status}")


def _reset_time(response: httpx.Response) -> datetime | None:
    try:
        return datetime.fromisoformat(response.json()["reset_time_utc"])
    except (ValueError, KeyError, TypeError):
        return None


def _is_usable(attributes: dict[str, Any]) -> bool:
    return (
        attributes.get("language") == ENGLISH
        and not any(attributes.get(flag) for flag in EXCLUDED_FLAGS)
        # Subtitles split over several files (CD1/CD2) do not fit a single movie file.
        and len(attributes.get("files", [])) == 1
    )


def _to_candidate(attributes: dict[str, Any]) -> SubtitleCandidate:
    [subtitle_file] = attributes["files"]
    return SubtitleCandidate(
        file_id=subtitle_file["file_id"],
        file_name=subtitle_file.get("file_name") or str(subtitle_file["file_id"]),
        download_count=attributes.get("download_count") or 0,
        hash_match=bool(attributes.get("moviehash_match")),
    )
