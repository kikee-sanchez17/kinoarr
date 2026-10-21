# Plan: Use the torrent's own subtitle, and never save another movie's subtitle

Implements [spec.md](spec.md).

## Dependencies
None new: only the standard library (`pathlib`, `re`, `unicodedata`). The copy reuses the existing safe write.

## Design

### Pure rules: `app/subtitles.py`
**Bundled subtitles**
- `bundled_subtitles(content_path: Path) -> list[Path]`
  - Returns `[]` when `content_path` is a file, meaning a single-file torrent.
  - Otherwise it returns every file under `content_path` (via `rglob`) with an extension in `SIDECAR_EXTENSIONS`.
  - It skips names whose tokens include forced or SDH tags (`FORCED_TAGS | SDH_TAGS`). Tokens are the name split on anything that isn't a letter or digit, so `2_English.SDH.srt` gives `2`, `english`, `sdh`.
  - Order: names with an English token (`en`, `eng`, `english`, held in `ENGLISH_NAME_TAGS`) first, then larger files first.
- `looks_english(text: str) -> bool`
  - It drops SRT cue numbers, timing lines and `<...>`/`{...}` formatting.
  - It splits the rest into lowercase words. Too short to judge (`MIN_WORDS_TO_JUDGE = 100`) gives `False`.
  - It returns `True` when at least `ENGLISH_WORD_SHARE = 0.25` of the words are in `COMMON_ENGLISH_WORDS`.
    - That set holds about 60 frequent English words that Spanish, French, Italian and German almost never use: the, and, you, what, that, this, with, have, don't, i'm, it's...
    - Words shared with those languages ("a", "no", "me", "he", "in", "son") are left out on purpose.
  - Real English dialogue scores about 0.4, other languages under 0.1. The tests fix these figures with real subtitle snippets.
- `read_subtitle_text(path: Path) -> str`
  - It decodes UTF-8 (with or without BOM) and UTF-16 (with BOM), and falls back to `cp1252`, the usual encoding for old Western subtitle files.
  - Only used for the check. The copy keeps the original bytes.
- `english_sidecar_path(video_path, extension=".srt")` gains the `extension` argument, so an `.ass` copy keeps `.ass`. The default keeps today's behaviour.

**Matching a result to the movie**
- `normalize_title(text: str) -> list[str]`
  - It applies NFKD and strips accents, turns `&` into `and`, and lowercases.
  - It splits on anything that isn't a letter or digit, so `The.Exorcism.of` gives `the`, `exorcism`, `of`.
- `matches_movie(title: str | None, year: int | None, names: list[str]) -> bool`
  - The title's words (leading `the`/`a`/`an` removed) must appear as a consecutive run in one of the names' words.
  - If `year` is set and that name contains a four-digit year (19xx or 20xx), one of the name's years must equal it.
  - `title=None` gives `False`, because a result that doesn't say its movie can't be trusted.
- `best_candidate` is unchanged: hash matches first, then most downloads. It now receives only the candidates that passed `matches_movie`.

### Models: `app/models.py`
- `SubtitleCandidate` gains `movie_title: str | None` and `movie_year: int | None`.
- `SubtitleFetchResult.status` becomes `Literal["downloaded", "already_present", "copied_from_torrent"]`. `subtitle_file` holds the copy's name for the new status.

### Client: `app/clients/opensubtitles.py`
`_to_candidate` fills `movie_title` and `movie_year` from `attributes["feature_details"]["title"]` and `["year"]`, which the real API returns (checked on 2026-10-21). A missing block gives `None`. Nothing else changes; the client stays a translator.

### Detection service: `app/services/subtitle_detection.py`
New method `bundled_subtitles(torrent_hash) -> list[Path]`.
- It reuses `_finished_torrent` and the path check, and calls the pure `bundled_subtitles(Path(torrent.content_path))`.
- `content_path` already went through path mapping in the qBittorrent client.
- `detect()` is unchanged.

### Fetch service: `app/services/subtitle_fetch.py`
`fetch()`, under the existing lock:
1. `report = detect(hash)`. If it already has English, return `already_present`, as today.
2. For each file from `bundled_subtitles(hash)`, if `looks_english(read_subtitle_text(file))`:
   - copy the file's bytes with `_write_atomically` to `english_sidecar_path(video, file.suffix.lower())`;
   - log `Copied subtitle X from torrent Y`;
   - return `copied_from_torrent`.

   If a file can't be read (`OSError`), log a warning and try the next one.
3. If there's no OpenSubtitles client, raise `SubtitleDownloadsDisabledError`, as today but only at this point.
4. `_find_candidate`:
   - hash search, then keep the results where `matches_movie(c.movie_title, c.movie_year, [torrent_name, video_stem])` holds;
   - if none is left, run the name search with the same filter;
   - log each skipped result at `INFO` (`Skipping OpenSubtitles result for 'Before I Fall' (2017): not 'The Exorcism…'`);
   - if still empty, raise `SubtitleNotFoundError`, as today.
5. Download and save, unchanged.

### Checker and startup
- `app/main.py`: `_start_subtitle_checker` always starts the checker. Without a key it logs once at `INFO`: "OPENSUBTITLES_API_KEY is not set: only subtitles included in torrents will be used".
- `app/services/subtitle_checker.py`: `SubtitleDownloadsDisabledError` joins `SubtitleNotFoundError` and `VideoNotFoundError` in the 24-hour retry branch, with an `INFO` line instead of an exception trace.

### API and UI
- `app/api/downloads.py`: no code change. The route returns the model, and the new status passes through.
- `app/static/app.js`: the subtitle message function gains `copied_from_torrent` → `Subtitle copied from the torrent: ${result.subtitle_file}`.

## Error handling
| Situation | Result |
|---|---|
| Bundled file unreadable | Warning logged, next file or OpenSubtitles |
| Bundled files present but none English | OpenSubtitles, as before |
| Copy can't be written | Existing `SubtitleWriteError` → `500` mentioning `PUID`/`PGID` |
| No API key and nothing bundled | `503` from the button, as today; checker retries in 24 h |
| OpenSubtitles results all for other movies | `404` "no English subtitle found", skipped ones logged |

## Testing strategy
- `tests/test_subtitles.py`:
  - `bundled_subtitles`: a folder with `Movie.srt`, `Subs/2_English.srt`, `Subs/3_English.SDH.srt`, `Subs/Spanish.srt` and `Movie.forced.srt`. Order and exclusions are checked, and a single file gives `[]`.
  - `looks_english`: real English, Spanish and French SRT snippets (a few hundred words each, written into the test); a tiny file; one with only timing lines.
  - `read_subtitle_text`: UTF-8 with BOM, UTF-16, cp1252 accents.
  - `matches_movie`: the Emily Rose and *Before I Fall* cases; *The Exorcism of God* rejected for the Emily Rose torrent; a missing leading "The"; accents and `&`; a different year; no year in the name; `None` title.
- `tests/test_opensubtitles_client.py`: `feature_details` mapped into the candidate, and missing details give `None`.
- `tests/test_subtitle_fetch_service.py` (fakes as today):
  - copied from the torrent: bytes identical, `.en.<ext>` name, OpenSubtitles never called;
  - a non-English bundled file falls through to OpenSubtitles;
  - a copy works without a client;
  - a hash result for another movie is skipped and the name search is used;
  - all results wrong give `SubtitleNotFoundError`.
- `tests/test_subtitle_detection_service.py`: `bundled_subtitles(hash)` for a torrent folder.
- `tests/test_subtitle_checker.py`: `SubtitleDownloadsDisabledError` schedules a 24-hour retry and logs no exception.
- `tests/test_downloads.py`: the endpoint returns `copied_from_torrent`.
- Startup: a test that the checker starts without an API key, if it fits the existing tests. Otherwise check it manually from the startup log line.
- Real API check (no quota used): search with hash `c333311f82a660b1` and the torrent name, and confirm the choice is an *Exorcism of Emily Rose* subtitle.
- Manual (home server, by the user): delete the wrong `.en.srt` and press "Get subtitles". Expect "copied from the torrent", identical text, and English in Jellyfin.
