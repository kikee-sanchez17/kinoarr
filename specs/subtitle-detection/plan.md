# Plan: Subtitle detection

Implements [spec.md](spec.md).

## Dependencies
None new. `ffprobe` (from `ffmpeg`) is already installed in the Docker image; it is called with `subprocess` from the standard library.

## ffprobe call
```
ffprobe -v error -select_streams s -print_format json
        -show_entries stream=index,codec_name:stream_tags=language,title:stream_disposition=forced,hearing_impaired
        <video file>
```
Returns `{"streams": [{"index": 2, "codec_name": "subrip", "tags": {"language": "eng", "title": "English SDH"}, "disposition": {"forced": 0, "hearing_impaired": 1}}, ...]}`. `tags` (and its keys) may be missing. The arguments are passed as a list (no shell), so file names with spaces or quotes are safe.

## Design

### Models (`app/models.py`)
```python
class SubtitleStream(BaseModel):
    """One embedded subtitle track, as ffprobe reports it."""
    index: int
    codec: str | None
    language: str | None
    title: str | None
    forced: bool
    hearing_impaired: bool

class FoundSubtitle(BaseModel):
    source: Literal["embedded", "sidecar"]
    description: str          # e.g. "track 2 (subrip, eng)" or "Movie.en.srt"

class SubtitleReport(BaseModel):
    torrent_hash: str
    video_path: str
    has_english_subtitle: bool
    english_subtitles: list[FoundSubtitle]
```

### `app/clients/ffprobe.py`
- `FfprobeError(Exception)`.
- `FfprobeClient(executable: str = "ffprobe")` with `subtitle_streams(video_path: Path) -> list[SubtitleStream]`.
  - `subprocess.run([...], capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_SECONDS, check=False)`; `FFPROBE_TIMEOUT_SECONDS = 60` (it only reads headers, but files on a NAS can be slow).
  - `FileNotFoundError` → "ffprobe not found: install ffmpeg"; timeout → "ffprobe timed out on <file name>"; non-zero exit → "ffprobe could not read <file name>: <first stderr line>"; invalid JSON → `FfprobeError`.
  - Converts each stream to `SubtitleStream` (`language`/`title` from `tags`, booleans from `disposition`).
- The subprocess call stays inside this class (side effects at the edge), so the rest is testable with a fake.

### `app/subtitles.py`: pure rules (no I/O except listing a folder)
- Constants: `VIDEO_EXTENSIONS`, `SIDECAR_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}`, `ENGLISH_TAGS = {"en", "eng"}`, `FORCED_TAGS = {"forced"}`, `SDH_TAGS = {"sdh", "hi", "cc"}`, `SDH_TITLE_MARKER = "sdh"`.
- `find_main_video(content_path: Path) -> Path | None`: if `content_path` is a video file, return it; if it is a folder, return the largest video file under it (recursive, since some torrents nest the movie one level down).
- `is_english_embedded(stream: SubtitleStream) -> bool`: language in `ENGLISH_TAGS`, not forced, not hearing impaired, title does not contain "SDH" (case-insensitive).
- `is_english_sidecar(subtitle_name: str, video_stem: str) -> bool`: extension in `SIDECAR_EXTENSIONS`; name starts with `video_stem + "."`; the dot-separated tags between them (lowercased) include an English tag and no forced/SDH tag.
- `english_sidecars(video_path: Path) -> list[Path]`: files in `video_path.parent` (not subfolders) that pass `is_english_sidecar`.
- These are small pure functions on purpose: the matching rules are where bugs hide, and they are tested with plain strings.

### `app/clients/qbittorrent.py`: `get_torrent(torrent_hash: str) -> Torrent | None`
- `torrents_info(torrent_hashes=torrent_hash)`; returns the first (mapped) `Torrent` or `None`. Shares the conversion with `list_torrents` (extract the existing list comprehension body into `_to_torrent`).

### `app/services/subtitle_detection.py`
```python
class TorrentNotFoundError(Exception): ...
class TorrentNotFinishedError(Exception): ...
class VideoNotFoundError(Exception): ...
class DownloadPathMissingError(Exception): ...

class SubtitleDetectionService:
    def __init__(self, qbittorrent_client, ffprobe_client) -> None: ...
    def detect(self, torrent_hash: str) -> SubtitleReport:
        # 1. get_torrent → TorrentNotFoundError
        # 2. progress < 1.0 → TorrentNotFinishedError
        # 3. Path(content_path) must exist → DownloadPathMissingError (message names the path-mapping variables)
        # 4. find_main_video → VideoNotFoundError
        # 5. ffprobe streams filtered with is_english_embedded + english_sidecars → SubtitleReport
```
- "Finished" means `progress >= 1.0`, the same rule `list_torrents(completed_only=True)` relies on in qBittorrent.

### `app/api/downloads.py`
- `GET /api/downloads/{torrent_hash}/subtitles`, `response_model=SubtitleReport`.
  | Exception | HTTP |
  |---|---|
  | `TorrentNotFoundError` | 404 |
  | `TorrentNotFinishedError` | 409 |
  | `VideoNotFoundError` | 422 |
  | `DownloadPathMissingError`, `FfprobeError` | 500 |
  | `QBittorrentError` | 502 |

### `app/dependencies.py`
- `get_ffprobe_client()` and `get_subtitle_detection_service()` with `@lru_cache`.

## Testing strategy
- `tests/test_subtitles.py` (pure functions, parametrized):
  - `is_english_sidecar`: `Movie.en.srt`, `Movie.eng.ass`, `Movie.EN.srt`, `Movie.en.default.srt` → true; `Movie.srt`, `Movie.en.forced.srt`, `Movie.en.sdh.srt`, `Movie.en.hi.srt`, `Movie.en.cc.vtt`, `Movie.es.srt`, `Movie.en.txt`, `Other.en.srt`, `Movie.2.en.srt` for video `Movie` (other movie) → false.
  - `is_english_embedded`: `eng`, `en`, `ENG` with no flags → true; forced, hearing impaired, title "English SDH", language `None`, `spa` → false.
  - `find_main_video` with `tmp_path`: single file, folder with sample + movie (largest wins), nested folder, folder with no video, non-video single file.
  - `english_sidecars` with `tmp_path`: finds beside the video, ignores `Subs/` subfolder.
- `tests/test_ffprobe_client.py`: `subprocess.run` replaced via `monkeypatch`; recorded JSON parsed into `SubtitleStream` (missing `tags`/`disposition` handled); not found, timeout, non-zero exit, bad JSON → `FfprobeError`; arguments passed as a list.
- `tests/test_qbittorrent_client.py`: `get_torrent` returns the mapped torrent, or `None`.
- `tests/test_subtitle_detection_service.py`: fakes for both clients plus `tmp_path` files; each error case and the happy path (embedded + sidecar combined).
- `tests/test_downloads.py`: route status codes with a fake service.

## Manual check
- Use the finished Internet Archive trailer in `dev-media/` (no subtitles) → `false`.
- Add/remove sidecars next to it (`.en.srt`, `.en.forced.srt`, `.srt`) and check the result each time; remove them afterwards.
- Generate a small `.mkv` with an English subtitle track using `ffmpeg` into the scratchpad and run `FfprobeClient` + the rules on it (proves the real ffprobe JSON matches the parser). Delete it afterwards.

## Risks / notes
- Releases sometimes tag English tracks wrongly or not at all; per the approved rule those count as missing, so Kinoarr may add a subtitle the user did not need. Acceptable: an extra `.srt` is harmless.
- Large folders on slow storage: `find_main_video` walks only the torrent's own folder, so cost is bounded by the torrent size.
