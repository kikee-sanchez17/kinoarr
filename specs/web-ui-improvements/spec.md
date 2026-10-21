# Spec: Web UI improvements

Status: Approved

## Goal
Make the web UI quicker to use after a search and give it a Jellyfin-like look: filter results by provider, resolution and video codec, show fewer and better results first, keep downloads in view, and add hover feedback and light animations.

## Context
The first version of the UI ([web-ui](../web-ui/spec.md)) works but is plain, lists up to 50 results before "Show more", and places the downloads list below them. Most of this change is in the browser. The one backend change: search results gain two fields read from the release title, `resolution` and `video_codec`, because Prowlarr does not return them as data.

## Requirements

### Layout
1. Order on the page: search box, then downloads, then search results (phone and desktop).

### Results
2. **Provider filter**: after a search, a row of buttons shows "All" and each indexer present in the results, each with its number of results (e.g. "All 196 · Internet Archive 100 · The Pirate Bay 86 · YTS 10"), indexers ordered by number of results. Clicking one shows only that indexer's results instantly, without a new search. The selected button is clearly marked. The row is hidden when the results come from a single indexer.
3. **Resolution and codec filters**: two more rows of buttons, built the same way:
   - Resolution: 2160p, 1080p, 720p, SD (480p/576p), Unknown, in that order.
   - Video codec: H.265, H.264, AV1, XviD/DivX, Unknown, in that order.
   - Each row shows only the values present in the results, with their counts over all results, and is hidden when the results have a single value.
   - The three filters combine: e.g. The Pirate Bay **and** 1080p **and** H.265. When no result matches, the page says "No results match these filters".
   - The results table gains a "Quality" column showing both values (e.g. "1080p · H.265", or "–"), so the user can see why a row matches.
   - Detection is a best guess from the release title (e.g. `x265`/`HEVC` → H.265, `4K`/`2160p` → 2160p). Titles that name neither are "Unknown"; most Internet Archive titles are.
4. **API**: each result from `GET /api/search` gains `resolution` (`"2160p"`, `"1080p"`, `"720p"`, `"SD"` or `null`) and `video_codec` (`"H.265"`, `"H.264"`, `"AV1"`, `"XviD/DivX"` or `null`). Existing fields are unchanged.
5. Each chosen filter value stays selected for the next search during the visit, if it appears in the new results; otherwise that filter goes back to "All". Reloading the page resets them.
6. **Fewer results first**: the 15 results with the most seeders (within the current filters) are shown; "Show more" adds the next 15 each time and disappears when nothing is left. This replaces the 50 of the web-ui spec. Changing the filter starts again from the first 15.
7. The status line says how many results are shown, e.g. "Showing 15 of 100 results".
8. **Compact table**: less padding and a slightly smaller font, so more rows fit on screen; buttons stay easy to tap on a phone.

### Look and feel
9. **Jellyfin-like look**:
   - Always dark, like Jellyfin's default theme (replaces "readable in both light and dark browser themes" from the web-ui spec).
   - Near-black background, dark grey surfaces, Jellyfin's blue as the accent for buttons, links, selected filter and progress bars.
   - The "Kinoarr" heading uses a purple-to-blue gradient, echoing Jellyfin's logo without copying it.
10. **Hover and animations**:
   - Buttons, filter buttons, links and result rows react on hover; buttons also on press; keyboard focus is clearly visible.
   - New results fade in; a download appears with a short fade-in the first time only (not on every 5-second refresh).
   - A small spinner shows while a search, a download request or a subtitle request is running.
   - A successful action ("Added", "Subtitle saved") is shown in a success colour.
   - Animations are short (under about 300 ms) and are turned off when the system asks for reduced motion.
11. Text and controls keep enough contrast to be readable (WCAG AA for body text).
12. No external fonts, images or other requests: the page stays self-contained.
13. Everything that works today keeps working, at phone width too (no horizontal scrolling).

## Acceptance criteria
- After a search for "night of the living dead", the filter shows All, Internet Archive, The Pirate Bay and YTS with their counts; choosing Internet Archive shows only its results, 15 at a time, most seeders first.
- "Show more" adds 15 rows each time and disappears at the end; changing the filter goes back to 15.
- "1080p" and "H.264" narrow the results to titles naming both; the counts match the titles; a combination with no match shows "No results match these filters".
- `GET /api/search` results include `resolution` and `video_codec`; unit tests cover the detection rules.
- A second search keeps "Internet Archive" selected if it has results, and falls back to "All" if it has none.
- The downloads list is visible above the results without scrolling (with a few downloads).
- Hovering buttons and rows gives visible feedback; a spinner shows while searching; downloads do not flash on each refresh.
- With "reduce motion" enabled in the system, nothing animates.
- The page is dark with Jellyfin-like colours whatever the system theme, and works at phone width.
- The page makes no requests other than to Kinoarr itself. All unit tests pass.

## Known limitations
- The filters only know the values in the current results; they cannot search a single indexer (a possible later feature using Prowlarr's indexer IDs).
- Resolution and codec come from the title, so they are only as good as the release name. The real file is only known after downloading.
- Counts are over all results, not over the results left by the other filters.

## Out of scope
- Other API changes; choosing the indexer before searching.
- Other title details (HDR, audio, source such as BluRay/WEB-DL).
- A logo image or favicon; a light theme or a theme switch.
- Remembering the filter across visits.

## Resolved questions
1. Filter: buttons built from the indexers in the results, filtered in the browser (approved).
2. Paging: 15 first, "Show more" adds 15 each time (approved).
3. Memory: the chosen filter values are kept during the visit only (approved).
4. Layout: downloads above results (approved). Density: compact (approved). Style: Jellyfin-like (approved).
5. Resolution and codec filters, detected from the title in the backend so the rules have unit tests (approved).
