# Tasks: Path mapping

Implements [plan.md](plan.md). Written retroactively; all tasks done.

## Implementation
- [x] 1. Write `app/path_mapping.py` with `map_path()` + `tests/test_path_mapping.py`.
- [x] 2. Replace `DOWNLOADS_PATH` with `QBITTORRENT_DOWNLOADS_PATH` and `KINOARR_DOWNLOADS_PATH` in `app/config.py`, `.env.example` and `/api/config`.
- [x] 3. Apply `map_path` to `save_path` and `content_path` in the qBittorrent client; pass the settings from `app/dependencies.py`.
- [x] 4. Add `tests/test_qbittorrent_client.py`.
- [x] 5. Run the full test suite: all green (24 passed).

## Review
- [x] 6. Review against `CLAUDE.md`: found that the code still used `QBIT_*` instead of `QBITTORRENT_*` and had Spanish text; fixed separately in commit `2e6fdfd`.
- [x] 7. Committed (`acefea5`, `426b62c`). This was before the "no commit without approval" rule existed.

## User actions
- [x] Update the local `.env`: rename `QBIT_*` to `QBITTORRENT_*`, replace `DOWNLOADS_PATH` with `QBITTORRENT_DOWNLOADS_PATH=/downloads` and `KINOARR_DOWNLOADS_PATH=<absolute path to dev-media>`.
