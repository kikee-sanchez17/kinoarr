# Spec: Use the torrent's own subtitle, and never save another movie's subtitle

Status: Approved

## Goal
When a download already ships a good English subtitle, Jellyfin should use it. When Kinoarr downloads one from OpenSubtitles, it must be for the same movie.

## Context
First real download on the home server: *The Exorcism of Emily Rose UNRATED (2005) [1080p]* (YTS). Its folder:
```
The.Exorcism.of.Emily.Rose.UNRATED.2005.1080p.BrRip.x264.BOKUTOX.YIFY.mp4
The.Exorcism.of.Emily.Rose.UNRATED.2005.1080p.BrRip.x264.BOKUTOX.YIFY.srt      ← from the torrent, English, in sync
The.Exorcism.of.Emily.Rose.UNRATED.2005.1080p.BrRip.x264.BOKUTOX.YIFY.en.srt   ← saved by Kinoarr: another movie
```
Two problems:
1. **The torrent's subtitle is ignored.** Detection only counts sidecars tagged as English (`Movie.en.srt`), by the rule in [subtitle-detection](../subtitle-detection/spec.md). Torrents also ship untagged files (`Movie.srt`), other names (`English.srt`) and `Subs/` folders. Jellyfin does not read `Subs/` folders, and shows an untagged file with an unknown language.
2. **OpenSubtitles gave a subtitle for another movie.**
   - A hash search for this file (`c333311f82a660b1`) returns 5 "exact" matches: 4 for *The Exorcism of Emily Rose (2005)* and 1 for *Before I Fall (2017)*. Someone linked that subtitle to the wrong file.
   - Kinoarr trusts every hash match and picks the most downloaded one, which is *Before I Fall* (251,742 downloads).
   - A name search has the same weakness: "The Exorcism of Emily Rose" lists *The Exorcism of God (2021)* first.
   - Every OpenSubtitles result says which movie it belongs to (title, year, IMDb ID), but Kinoarr does not check it.

## User stories
- As a user, when the torrent includes an English subtitle, Jellyfin shows it as "English" and Kinoarr does not spend an OpenSubtitles download.
- As a user, a subtitle Kinoarr downloads is always for the movie I downloaded. When it cannot find one for that movie, it says so instead of saving a wrong one.

## Requirements

### Subtitles that come with the torrent
1. Before searching OpenSubtitles, Kinoarr looks for subtitle files (`srt`, `ass`, `ssa`, `vtt`) anywhere inside the torrent's folder. Files whose name marks them as forced or SDH are skipped.
   - A single-file torrent has no folder of its own, so there is nothing to look for.
   - Files beside other movies in the same downloads folder are never considered.
2. A file is used only when its **text is English**. Kinoarr reads it and checks it with a simple word-based test, without new dependencies. Names that say English (`en`, `eng`, `english`) are tried first, then larger files, because a full subtitle is bigger than a forced one.
3. The chosen file is **copied** next to the movie as `<movie name>.en.<extension>`, written safely like downloaded subtitles. The original is left untouched, so qBittorrent keeps seeding. Jellyfin then lists the subtitle as English; it may also list the original as "Unknown", which is acceptable.
4. `POST /api/downloads/{hash}/subtitles` answers `status: "copied_from_torrent"` with the new file name. The web UI shows "Subtitle copied from the torrent: <file>".
5. This works without an OpenSubtitles API key.

### Matching OpenSubtitles results to the movie
6. An OpenSubtitles result is used only if its movie matches the download.
   - The result's title must appear in the torrent name or in the video file name. Case, punctuation, accents and a leading "The", "A" or "An" are ignored.
   - When both the result and the name have a year, the years must be equal.
7. This applies to hash searches and name searches. If every hash result is for another movie, Kinoarr falls back to the name search, as it does when the hash finds nothing.
8. When no result matches, Kinoarr reports "no English subtitle found" (`404`) rather than saving a doubtful one. The background checker retries after 24 hours, as today.
9. Results that are skipped for being another movie are logged at `INFO` with their title and year, so a wrong link on OpenSubtitles is visible in `docker logs kinoarr`.

### Background checker
10. The checker runs even without an OpenSubtitles API key, so it still copies subtitles that come with torrents. Without a key, a download that has no usable subtitle in the torrent is retried after 24 hours, with one `INFO` line rather than an error each round.

### Unchanged
- Detection (`GET /api/downloads/{hash}/subtitles`) still counts only embedded English tracks and sidecars tagged as English. A torrent whose subtitle has been copied is reported as having one.
- Kinoarr never deletes or renames files it did not create.

## Acceptance criteria
- Unit tests cover:
  - the English text check (English passes; Spanish, French and nearly empty files fail);
  - the choice among bundled files (English name first, larger first, forced and SDH skipped, single-file torrents);
  - the title and year match, including this case: *Before I Fall (2017)* is rejected for "The Exorcism of Emily Rose UNRATED (2005) [1080p]", and *The Exorcism of Emily Rose (2005)* is accepted;
  - the new fetch order (already present → copied from torrent → OpenSubtitles);
  - the checker without an API key;
  - the new status in the API and in the UI message.
- On the home server, after deleting the wrong `…YIFY.en.srt` by hand, "Get subtitles" on *The Exorcism of Emily Rose* answers "Subtitle copied from the torrent". The new `.en.srt` has the same text as the torrent's `.srt`, and Jellyfin lists it as English.
- With the same file's hash, the OpenSubtitles choice is an *Exorcism of Emily Rose* subtitle. This is checked here with the real API: searches don't use the download quota.

## Known limitations
- The English check is a heuristic. A file that mixes languages, or has very little text, may be rejected, and OpenSubtitles is used instead.
- Title matching depends on the torrent name. Very unusual names, such as translated titles or abbreviations, may match nothing, and the user then gets "not found" instead of a subtitle.
- Detection still does not count untagged subtitles, so `GET …/subtitles` says "no English subtitle" until the copy is made.

## Out of scope
- Using the IMDb ID that some indexers return, to match OpenSubtitles results exactly. This would need Kinoarr to remember it per torrent.
- Checking that a subtitle is in sync with the video.
- Replacing a subtitle that Kinoarr saved earlier. The user deletes it by hand.
- Languages other than English.

## Resolved questions
1. New API status `copied_from_torrent` (approved).
2. The checker runs without an API key (approved).
3. When nothing matches the movie: report "not found" (approved).
4. The bundled file is copied, not renamed, so seeding keeps working. A duplicate "Unknown" entry in Jellyfin is fine (approved).
5. Logging: no change needed. Kinoarr's `INFO` lines already reach the logs; the empty output came from running `docker compose logs` in another folder.
