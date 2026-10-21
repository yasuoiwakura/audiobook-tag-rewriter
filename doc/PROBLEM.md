# Problem: Incorrect Audiobookshelf Import of AudioBookConverter M4Bs

Status: documented; workaround implemented<br>
Last updated: 2026-10-21

## 1. Summary

AudioBookConverter writes series audiobooks with a different tag semantics than
Audiobookshelf (ABS) expects for M4B files:

- `album` = series
- `track` = series sequence
- `title` = book title

For M4B, Audiobookshelf uses `album` as the book title and `track` as the
track/chapter. The ffprobe-based scanner only reads the series and series sequence
from `show` and `episode_id`, which come from the MP4 atoms `tvsh` and `tven`.

That alone would be solvable by writing `mvnm`/`mvin`. However, ABS invokes
ffprobe without `-export_all`. As a result, `mvnm`/`mvin` are invisible to ABS for
MP4/M4B. The outcome: the book title lands in the wrong field, and series and
series sequence remain empty.

## 2. Symptoms

After importing an affected `.m4b` file into Audiobookshelf:

- The book title is empty or matches the album/series name.
- The series is empty.
- The series sequence is empty.
- `track` is shown as a chapter/track even though it is the series sequence.
- The file has to be fixed manually in ABS.

## 3. Root-Cause Chain

1. **AudioBookConverter tag semantics**
   - `album = series`
   - `track = series sequence`
   - `title = book title`

2. **Audiobookshelf mapping for M4B**
   - `album` → book title
   - `track` → track/chapter
   - `show` → series
   - `episode_id` → series sequence

3. **ffprobe behavior for MP4/M4B**
   - `tvsh`/`tven` are exported as `show`/`episode_id` and are visible to ABS.
   - `mvnm`/`mvin` are unknown atoms to the MOV/MP4 demuxer.
   - Without `-export_all`, they do not appear in `format.tags`.

4. **Consequence**
   - The documented ABS mapping `mvnm`/`mvin` does not work for M4B.
   - The existing values from `album`/`track` are interpreted incorrectly.

## 4. Evidence

The upstream issue draft [`ABS-issue-readtags.md`](../ABS-issue-readtags.md)
contains the full ffprobe examples. Short version:

```powershell
# Without -export_all: mvnm/mvin are missing
ffprobe.exe -v quiet -show_entries format_tags -of json -- "file.m4b"

# With -export_all: mvnm/mvin are visible
ffprobe.exe -v quiet -export_all 1 -show_entries format_tags -of json -- "file.m4b"
```

Example output with `-export_all`:

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

Relevant ABS sources:

- `server/libs/nodeFfprobe/index.js` (ffprobe call without `-export_all`)
- `server/utils/prober.js` (mapping `series/show/mvnm`, `series-part/episode_id/mvin`)
- `server/scanner/AudioFileScanner.js`

## 5. Decision

The fix is applied **at file level in a copy**, not by patching ABS:

- `album` is copied to `series` and written as `tvsh` + `mvnm`.
- `track` is copied to `series-part` and written as `tven` + `mvin`.
- `album` is then set to `title`.

This supports both worlds:

- `tvsh`/`tven` are visible to ABS and ffprobe without `-export_all`.
- `mvnm`/`mvin` remain available for other players (Plex, Apple ecosystem, etc.).

The source file remains unchanged in the default mode. In-place overwriting is a
separate option that must be enabled explicitly.

## 6. Rejected Alternatives

| Alternative | Why not |
| --- | --- |
| Patch or fork ABS | Maintenance burden, upstream conflict, affects all users |
| Wait for an upstream fix only | Blocks the import indefinitely |
| Set ABS metadata via API after import | Not file-portable, no solution for other players |
| Overwrite all files directly in the ABS library | No idempotency marker, unnecessary write load, scan races |
| Write only `mvnm`/`mvin` | Invisible to ABS for M4B |

## 7. Scope and Non-Goals

**Scope:**

- Batch processing of `.m4b` files.
- Tag-to-tag mapping and exact value replacements.
- Optional backup, suffix, same-directory mode, recursive structure, and
  in-place overwrite.
- Docker operation as a sidecar in front of an ABS library.

**Non-goals:**

- Re-encoding or remuxing audio data.
- Library management, metadata matching, or cover downloads.
- Direct manipulation of the ABS database.
- Guaranteed correct results for non-AudioBookConverter sources.
- Automatic deletion or moving of source files.

## 8. Limits and Risks

- **Full copy:** Every processed file is copied in full, even if no tags change.
  For large M4Bs this costs time and storage.
- **MP4 layout:** If `moov` precedes `mdat`, growing a tag can shift the `mdat`
  block.
- **Source assumption:** The default mapping is designed for the
  AudioBookConverter files described in the issues. Other sources need their own
  `TAG_MAP`.
- **Upstream still open:** The ffprobe/`-export_all` fix belongs to
  Audiobookshelf. This project is a workaround, not an upstream solution.
- **No ABS integration test:** The tests use synthetic M4B files. A real ABS scan
  is not part of the automated test suite.

## 9. Upstream

- [`ABS-issue-readtags.md`](../ABS-issue-readtags.md) – draft for the
  Audiobookshelf issue.
- [AudioBookConverter #759](https://github.com/yermak/AudioBookConverter/issues/759)
- [Audiobookshelf #5669](https://github.com/advplyr/audiobookshelf/issues/5669)
- [Audiobookshelf #2471](https://github.com/advplyr/audiobookshelf/issues/2471)

## 10. References

- [Audiobookshelf: Book Library Structure](https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/)
- [Audiobookshelf: Docker installation](https://audiobookshelf.org/docs/documentation/install/docker/)
- [`SPEC.md`](../SPEC.md) – implementation status and acceptance criteria
- [`ARCHITECTURE.md`](ARCHITECTURE.md) – technical flow
- [`CONFIGURATION.md`](CONFIGURATION.md) – all options
- [`OPERATIONS.md`](OPERATIONS.md) – operations and troubleshooting
