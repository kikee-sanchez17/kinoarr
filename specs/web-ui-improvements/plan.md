# Plan: Web UI improvements

Implements [spec.md](spec.md).

## Dependencies
None. Plain CSS transitions and keyframes; no animation library; `re` from the standard library.

## Backend: resolution and codec from the title

### `app/release_title.py` (new, pure functions)
```python
Resolution = Literal["2160p", "1080p", "720p", "SD"]
VideoCodec = Literal["H.265", "H.264", "AV1", "XviD/DivX"]

def detect_resolution(title: str) -> Resolution | None: ...
def detect_video_codec(title: str) -> VideoCodec | None: ...
```
- Each is an ordered list of `(value, compiled regex)` pairs; the first match wins. Case-insensitive.
- Resolution: `2160p|4k|uhd` → 2160p; `1080p|1080i` → 1080p; `720p` → 720p; `576p|480p` → SD.
- Codec, H.265 checked before H.264: `x.?265|h.?265|hevc` → H.265; `x.?264|h.?264|avc` → H.264; `av1` → AV1; `xvid|divx` → XviD/DivX.
- Patterns only match whole tokens (not inside other words or numbers), so e.g. "1720p", "avclub" or "4kids" do not match. Release names separate tokens with dots, spaces, dashes, underscores or brackets, so a token boundary is "not a letter or digit" (`(?<![a-z0-9])…(?![a-z0-9])`) rather than `\b`, which treats `_` as part of a word.
- Why a module of its own: it is Kinoarr's own parsing of release names, not Prowlarr's API, so it does not belong in the client; and as pure functions it is easy to test.

### `app/models.py`, `app/services/search.py`
- `SearchResult` gains `resolution: Resolution | None` and `video_codec: VideoCodec | None`.
- `_without_download_links()` becomes `_to_search_result()`, filling the two fields from the title.

## Design

### `app/static/index.html`
- Order: header, search section (form + status), downloads section, results section (filter row, table, "Show more").
- Header text in `<span class="brand">` for the gradient.
- New empty `<div id="result-filters" class="filters" hidden>`; its rows and buttons are built by `app.js` (each row a `role="group"` with an `aria-label`).

### `app/static/app.js`
**State** (replaces `resultsNotShown`):
```js
const RESULTS_PAGE_SIZE = 15;
const ALL_INDEXERS = null;
let allResults = [];               // last search, in API order (most seeders first)
// One entry per filter row; the chosen value is kept across searches during the visit.
const FILTERS = [
  { key: "indexer", label: "Indexer", order: "count" },
  { key: "resolution", label: "Resolution", order: ["2160p", "1080p", "720p", "SD", null] },
  { key: "video_codec", label: "Codec", order: ["H.265", "H.264", "AV1", "XviD/DivX", null] },
];
const selectedValues = new Map(); // filter key -> chosen value (absent = All)
let shownResultsCount = 0;
const knownDownloadHashes = new Set(); // to fade in only new downloads
```
**Functions**
- `renderResults(results)`: stores `allResults`; drops any selected value that no result has; then `renderFilters()` and `showFirstPage()`.
- `countValues(results, key, order)` (pure): `[value, count]` pairs for the values present, in the filter's fixed order, or most results first (ties by name) for `"count"`. `null` is shown as "Unknown".
- `filteredResults()`: `allResults` that match every selected value.
- `renderFilters()`: one row per filter (label + "All N" + a pill per value, `aria-pressed` on the selected one); a row is hidden when it has a single value. Clicking sets or clears the value, re-renders the filters, and calls `showFirstPage()`.
- `showFirstPage()`: clears the table body, `shownResultsCount = 0`, then `showNextPage()`.
- `showNextPage()`: appends the next `RESULTS_PAGE_SIZE` rows of `filteredResults()`, updates the status ("Showing X of Y results", or "No results match these filters") and hides "Show more" when all are shown.
- Status and spinner: `setStatus(element, text, kind)` with `kind` one of `"info"`, `"busy"`, `"success"`, `"error"` (replaces the `isError` flag). `"busy"` adds a CSS spinner before the text. Used for "Searching…", "Adding…", "Looking for subtitles…", and the success messages.
- Subtitle messages store `{ text, kind }` instead of `{ text, isError }`.
- `createDownloadItem()`: adds class `is-new` when the hash is not in `knownDownloadHashes`, then records it, so the fade-in runs only the first time a download appears.

### `app/static/style.css`
**Colours**: one dark set, `color-scheme: dark`, no `prefers-color-scheme` block.
| Token | Value | Use |
|---|---|---|
| `--background` | `#101010` | page |
| `--surface` | `#1c1c1c` | table, download cards |
| `--surface-raised` | `#262626` | table header, inputs, row hover |
| `--text` | `#e8e8e8` | body text |
| `--text-muted` | `#a3a3a3` | captions, states |
| `--border` | `#2e2e2e` | dividers |
| `--accent` | `#00a4dc` | Jellyfin's blue |
| `--accent-hover` | `#2bb8eb` | buttons on hover |
| `--accent-text` | `#0b0b0b` | text on accent buttons |
| `--brand-gradient` | `linear-gradient(90deg, #aa5cc3, #00a4dc)` | header text |
| `--success` | `#4ade80` | success messages |
| `--error` | `#ff6b6b` | error messages |
| `--transition` | `150ms ease` | shared timing |

Contrast checked with a WCAG calculator before finishing.

**Components**
- Header: gradient text (`background-clip: text`), plain accent as fallback.
- Font stack: `"Noto Sans", system-ui, …` (used only if installed locally).
- Buttons: background/border colour transition on hover, `transform: scale(0.97)` while pressed, `:focus-visible` outline in the accent colour.
- Filter buttons: pill-shaped, outline style; hover lightens the border; selected (`aria-pressed="true"`) filled with the accent. The count is shown in a lighter weight.
- Compact table: cell padding `4px 8px`, table font `0.9rem`; row hover on `--surface-raised`; desktop table buttons `4px 10px`; at phone width buttons at least 36px tall.
- Inputs: border turns accent on focus.
- Animations: `@keyframes fade-in` (opacity 0→1, `translateY(4px)`→0, 200 ms) on result rows and `.download.is-new`; `@keyframes spin` for the spinner (a small bordered circle, `::before` of `.status.busy`).
- `@media (prefers-reduced-motion: reduce)`: animation and transition durations set to near zero.

## Testing strategy
- New `tests/test_release_title.py`: parametrized real-world titles for each resolution and codec (including the dev search results seen so far), H.265 winning over H.264 when both appear, case-insensitivity, separators (dots, spaces, dashes, underscores, brackets), no match inside other words/numbers, and `None` when the title names nothing.
- `tests/test_search_service.py`: results carry `resolution` and `video_codec` from their titles.
- Existing tests keep passing (`tests/test_web_ui.py` checks the page and assets load).
- No JavaScript tests (as decided in the web-ui spec); pure helpers (`countValues`, `filteredResults`) are kept small.
- Visual checks: headless Firefox screenshots at 1280px and 390px for the static layout; the user checks a real search, the filter, "Show more", a download and hover in the browser.
