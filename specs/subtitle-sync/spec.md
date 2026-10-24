# Spec: Subtitles in sync with the movie

Status: Approved

## Goal
A subtitle Kinoarr downloads from OpenSubtitles should be in sync with the movie file, not just made for the same movie.

## Context
On the home server, *Lady Bird (2017) [BluRay] [1080p] [YTS.AM]* got an OpenSubtitles subtitle that is about 8 seconds early at minute 2.
- The video is 23.976 fps (`24000/1001`, checked with ffprobe), the usual rate for a BluRay rip.
- A YTS file almost never has an OpenSubtitles hash match, so Kinoarr falls back to the name search and takes the **most downloaded** result.
- A name search for "lady bird 2017" (checked on 2026-10-24, no quota used) returns 50 results. The most downloaded one is `Lady Bird 2017 DVDScr XVID AC3 HQ Hive-CM8`: a pre-release screener, listed at **30 fps**. Several BluRay subtitles at 23.976 fps follow, e.g. `Lady.Bird.2017.720p.BluRay.x264.DTS-HDC`.
- Every result already says which release it was made for (`release`) and its frame rate (`fps`), but Kinoarr ignores both.
- The log says "Saved subtitle X", but not whether it was a hash match or which release it was for, so a bad choice can't be explained afterwards.

A subtitle is timed for one release. Other releases of the same movie can have a different intro or cut (a constant offset or a jump at some point) or a different frame rate (a gap that grows over the movie). Choosing a better subtitle avoids most of this. Re-timing the chosen one against the movie's audio fixes most of the rest.

## User stories
- As a user, the subtitle Kinoarr downloads is for my release when one exists, not a screener or a different-speed copy.
- As a user, when only a subtitle for another release exists, Kinoarr adjusts its timing to my movie's audio, so I don't have to shift it in Jellyfin.
- As a user (or someone helping me), I can see in `docker logs kinoarr` which subtitle was chosen and why.

## Requirements

### Choosing the OpenSubtitles result
1. Among the results that pass the existing movie check ([subtitle-matching](../subtitle-matching/spec.md)), Kinoarr prefers, in this order:
   1. a file-hash match (as today);
   2. not a pre-release copy: subtitles whose release name marks a cam, telesync, telecine or screener (`CAM`, `TS`, `TC`, `DVDScr`, `Screener`, `R5`...) come last;
   3. the same frame rate as the video. A subtitle with no frame rate (`0`) ranks between a match and a mismatch. Frame rates within 0.01 fps count as equal;
   4. the same source as the download (BluRay, WEB, DVD, HDTV), read from the subtitle's release name and from the torrent or file name;
   5. the same release group (e.g. `YTS`/`YIFY`, `RARBG`);
   6. the most downloads (as today).
2. Results are never dropped by these rules, only ranked. A mismatched subtitle is still better than none, and requirement 4 can fix its timing.
3. If the video's frame rate can't be read, that rule is skipped. The fetch doesn't fail.

### Logging the choice
4. When a subtitle is saved from OpenSubtitles, one `INFO` line says whether it was a hash or name match, and gives its release name, its frame rate and the video's frame rate.

### Re-timing to the audio
5. A subtitle downloaded from OpenSubtitles **without** a hash match is re-timed to the movie's audio with [alass](https://github.com/kaegi/alass) before it is saved. alass detects speech in the audio and moves the subtitle lines to fit it. It handles a constant offset, a cut or extra scene in the middle, and a different frame rate.
6. Hash matches and subtitles copied from the torrent are saved as they are: they were made for this exact file.
7. If alass is missing, fails or takes too long, Kinoarr saves the subtitle without re-timing and logs a warning. A subtitle that may be off is better than none.
8. The Docker image includes alass. A native install works without it (requirement 7). The README will say how to add it.
9. `POST /api/downloads/{hash}/subtitles` answers with a new field `synced_to_audio` (`true` or `false`). The web UI shows "Subtitle saved and synced to the audio: <file>" when it is `true`.
10. Re-timing takes time (alass reads the movie's audio). The "Get subtitles" button keeps showing "Looking for subtitles…" until it finishes. Other requests and the downloads list keep working meanwhile.

### Unchanged
- The movie check, the torrent's own subtitle first, quota handling and retries.
- Kinoarr never changes files it did not create.

## Acceptance criteria
- Unit tests cover:
  - the new ranking, including the real Lady Bird case: for a 23.976 fps BluRay YTS file, the screener at 30 fps is not chosen and a 23.976 fps BluRay subtitle is;
  - source, pre-release and group detection from release names;
  - reading the frame rate with ffprobe (`24000/1001` → 23.976, missing or `0/0` → none);
  - re-timing used for name matches only; a failure or a missing alass keeps the original subtitle;
  - the new `synced_to_audio` field and the UI message.
- Local check with an Internet Archive download: a subtitle shifted by hand by 8 seconds comes back in sync after alass. Time and peak memory are noted in `task.md`.
- On the home server, after deleting Lady Bird's current `.en.srt` by hand: "Get subtitles" saves a BluRay subtitle, synced to the audio, and the first line ("Do you think I look like I'm from Sacramento?") shows when it is spoken. Time and memory are noted.

## Known limitations
- alass can be wrong on films where speech runs over constant music (a test documentary got worse even from an in-sync subtitle), or when the subtitle covers much less or more than the movie (another cut).
- A subtitle from a slower release (23.976 fps) on a faster video (25 fps) is not fixed; the opposite, more common case is. The frame-rate ranking avoids both when a matching subtitle exists.
- Re-timing reads the whole audio track. Measured locally: about 1 s and 71 MB for a 75-minute movie with a light audio track; a BluRay audio track will take longer.
- alass's last release is from 2019. It is a single static binary with no other dependencies, so this is acceptable, but it won't get fixes.
- The image includes alass for amd64 only, like the published image.

## Out of scope
- Letting the user choose among several OpenSubtitles results. Possible later; each try costs a download from the daily quota.
- Re-timing subtitles that are already beside the movie, or replacing a subtitle Kinoarr saved earlier. The user deletes it by hand and presses "Get subtitles" again.
- Using an embedded subtitle in another language as alass's reference instead of the audio.
- Exposing alass's tuning options as settings.

## Resolved questions
1. API shape: new field `synced_to_audio: bool` in the `POST …/subtitles` response (approved).
2. Only name matches from OpenSubtitles are re-timed; hash matches and torrent copies are not (approved).
3. When alass fails, is missing or times out: save the subtitle without re-timing and log a warning (approved).
4. Configuration: no new variable for now; alass is used when it is on the `PATH`. Revisit after measuring its cost on the home server; adding an on/off variable would be asked first.
5. Pre-release subtitles are ranked last, not dropped (approved).
