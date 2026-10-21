# M4B: Series/Series Sequence not imported from `mvnm`/`mvin` because the ffprobe wrapper omits `-export_all`

> This is a draft for an upstream Audiobookshelf issue. The project-level problem
> statement, scope and chosen workaround are documented in
> [`doc/PROBLEM.md`](doc/PROBLEM.md).

## Summary

The ABS documentation maps:

- `series / mvnm` → Series
- `series-part / mvin` → Series Sequence

For MP4/M4B files these tags are not seen by the ffprobe-based scanner. The
ABS ffprobe wrapper does not pass `-export_all`, so ffprobe omits unknown MP4
atoms such as `mvnm` and `mvin` from `format.tags`. As a result, Series and
Series Sequence remain empty after a scan.

This works for MP3/ID3 files because `mvnm`/`mvin` are native ID3 frames there
and are exposed by ffprobe without `-export_all`.

## Environment

- Audiobookshelf: v2.33.2 (reported), ffprobe-based scanner
- ffprobe: `ffmpeg-2026-10-19-git-2344518cc5-essentials_build`
- File: M4B, MP4/M4A container, ~834 MB
- Example file: `Vasily Mahanenko - [Galaktogon - 3] - ... (Thomas Balou Martin).m4b`
- Tags present in the file: `mvnm = Galaktogon`, `mvin = 3`

## Steps to reproduce

1. Add the MP4 atoms `mvnm` and `mvin` to an M4B file, e.g. with beets-audible,
   MP3tag or mutagen.

2. Read tags with ffprobe **without** `-export_all`:

   ```powershell
   ffprobe.exe -v quiet -show_entries format_tags -of json -- "file.m4b"
   ```

   Result: `mvnm` and `mvin` are missing. Only standard tags such as `title`,
   `album`, `track`, `date` and `genre` are returned.

3. Run the same command **with** `-export_all`:

   ```powershell
   ffprobe.exe -v quiet -export_all 1 -show_entries format_tags -of json -- "file.m4b"
   ```

   Result: `mvnm` and `mvin` are present:

   ```json
   {
     "format": {
       "tags": {
         "title": "Ein Scheck über eine Milliarde (Ungekürzt)",
         "artist": "Vasily Mahanenko",
         "album": "Ein Scheck über eine Milliarde (Ungekürzt)",
         "track": "3",
         "mvin": "3",
         "mvnm": "Galaktogon"
       }
     }
   }
   ```

4. Scan the file in ABS.

## Expected behavior

ABS populates:

- Series = `Galaktogon`
- Series Sequence = `3`

## Actual behavior

- Series and Series Sequence remain empty.
- `album` is used as the book title.
- `track` is used as the track/chapter.

The documented `mvnm`/`mvin` mapping does not work for this M4B file.

## Root cause

The ABS ffprobe wrapper in `server/libs/nodeFfprobe/index.js` spawns ffprobe
with:

```text
-hide_banner -loglevel fatal -show_error -show_format -show_streams
-show_programs -show_chapters -show_private_data -print_format json <file>
```

`-export_all` is missing.

ffprobe does not export unrecognized MP4 atoms by default. `mvnm` and `mvin`
are unknown to the MOV/MP4 demuxer and only appear with `-export_all`.
The existing `-show_private_data` flag is not sufficient for this.

The ABS parser in `server/utils/prober.js` does contain the expected mappings:

```text
file_tag_series:     series, show, mvnm
file_tag_seriespart: series-part, episode_id, mvin, part
```

Because ffprobe never returns `mvnm`/`mvin` for MP4 without `-export_all`,
these fallbacks can never match.

## Suggested fixes

1. **Add `-export_all` to the ffprobe call** (preferred, but test for side
   effects):

   ```text
   -export_all 1
   ```

   This makes `mvnm`/`mvin` available in `format.tags` and the existing
   `prober.js` mapping can handle them.

2. **Use a targeted second ffprobe call only when the series is missing.**
   Run the normal probe first; if `series`/`show`/`mvnm` is absent, run a second
   probe with `-export_all 1 -show_entries format_tags`. This avoids exposing
   additional unknown tags in the normal case.

3. **Clarify the documentation.** For MP4/M4B, the currently working tags are
   `tvsh`/`tven` (ffprobe: `show`/`episode_id`), because ABS already maps those
   keys. `mvnm`/`mvin` are only reliably visible for ID3 files with the current
   ffprobe invocation.

4. **Add a regression test.** Include a small M4B/M4A fixture with
   `mvnm`/`mvin` and assert that Series/Series Sequence are populated.

## Workaround for users and tag-writing tools

Until this is fixed, writers can additionally set:

- Series: MP4 `tvsh` → ffprobe `show` → ABS Series
- Series Sequence: MP4 `tven` → ffprobe `episode_id` → ABS Series Sequence

`mvnm`/`mvin` can still be written in parallel for other players
(Plex, Apple ecosystem, etc.).

## Why the debug command from issue #759 is misleading

The command used there:

```powershell
ffprobe.exe -v quiet -show_entries format_tags -of json "file.m4b"
```

does not show `mvnm`/`mvin` for M4B. This does not mean the tags are missing;
ffprobe simply does not export them without `-export_all`.

To inspect the raw tags:

```powershell
ffprobe.exe -v quiet -export_all 1 -show_entries format_tags -of json -- "file.m4b"
```

## Related issues

- #2471: Support "movementname" and "movement" fields to match mvin and mvnm
- #5669: Separate mapping for M4B files
- AudioBookConverter #759: Metadata mismatch on Audiobookshelf import

## Additional information

- ABS documentation:
  <https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/>
- Relevant ABS files:
  - `server/libs/nodeFfprobe/index.js`
  - `server/utils/prober.js`
  - `server/scanner/AudioFileScanner.js`
