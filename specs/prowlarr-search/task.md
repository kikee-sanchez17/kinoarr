# Tasks: Prowlarr movie search

Implements [plan.md](plan.md). Tick each task when done.

## Setup
- [x] 1. Add the `prowlarr` service to `docker-compose.dev.yml`.
- [x] 2. (User) Start it, add the Internet Archive indexer, put `PROWLARR_URL` and `PROWLARR_API_KEY` in `.env`.
- [x] 3. Call the real search API once and confirm the JSON field names match the plan. (Confirmed via OpenAPI schema; found nullable fields, empty-list-on-failure and slow searches; spec and plan updated.)

## Implementation
- [x] 4. Add `Release` and `SearchResult` to `app/models.py`.
- [x] 5. Write `app/clients/prowlarr.py` (`ProwlarrClient`, `ProwlarrError`) + `tests/test_prowlarr_client.py`.
- [x] 6. Write `app/services/release_store.py` + `tests/test_release_store.py`.
- [x] 7. Write `app/services/search.py` + `tests/test_search_service.py`.
- [x] 8. Add `get_prowlarr_client()`, `get_release_store()`, `get_search_service()` to `app/dependencies.py`.
- [x] 9. Write `app/api/search.py`, register it in `app/main.py` + `tests/test_search.py`.
- [x] 10. Run the full test suite: all green, none skipped (46 passed).

## Verification
- [x] 11. Manual check of every acceptance criterion in `spec.md` against the dev Prowlarr (all pass; "Prowlarr stopped" simulated with a closed port).

## Review (before committing)
- [x] 12. Review the diff against `CLAUDE.md`:
  - Decisions respected (FastAPI, Prowlarr, movies only, no auth, no Jellyfin calls).
  - Configuration only through env vars; nothing hardcoded; `.env.example` updated if a variable changed.
  - Clean code: clear names, no abbreviations or magic values, small functions, type hints, Pydantic models.
  - Separation of concerns: thin route, external API in its own client.
  - Errors: specific exceptions, clear HTTP errors, no secrets in logs or messages.
  - No new dependencies (or approved by the user).
  - Every behavior change has tests; nothing failing or skipped.
  - Code, comments and docs in English.
- [x] 13. Explain the changes to the user and wait for approval.
- [x] 14. Commit only when the user says so.
