# SPEC – m4b-tag-fixer

Last updated: 2026-10-21<br>
Version: 0.1.0<br>
Status: working MVP; ABS series mapping, copy/suffix mode, input backup,
directory-structure mirroring, and in-place overwrite implemented

## 1. Purpose

`m4b-tag-fixer` reads and writes MP4 metadata in `.m4b` audiobook files. The goal
is to prepare tags produced by AudioBookConverter so that Audiobookshelf (ABS)
correctly imports title, author, narrator, series, and series sequence.

The problem, root-cause chain, and rejected alternatives are documented in
[`doc/PROBLEM.md`](doc/PROBLEM.md).

In the default mode, source files are not modified; a copy is edited. With
`OVERWRITE_SOURCE_FILE=true`, the source can be explicitly overwritten in place;
a backup is strongly recommended.

## 2. Current Implementation

### 2.1 Processing

- Default input: `/in`
- Default output: `/out`
- Docker: `/data/in` (AudioBookConverter) → `/data/out` (Audiobookshelf)
- Docker backup: `/data/backup`
- Alternative: copy in the source folder with a suffix (`OUTPUT_SAME_DIR=true`)
- File discovery: `.m4b` only, optionally recursive
- Optional recursive search with source-structure mirroring
  (`REPLICATE_SOURCE_DIR_STRUCTURE=true`); file names remain unchanged
- Optional `OUTPUT_SUFFIX=true` to always append `RENAME_SUFFIX`
- Optional in-place overwrite of the source (`OVERWRITE_SOURCE_FILE=true`); a
  backup is strongly recommended
- File name filter: glob, case-insensitive, default `*.m4b`
- No re-encoding of audio data
- Optional backup of the input file before processing (`BACKUP=true`)

Per-file flow:

1. Read source tags.
2. Compute mappings and value replacements in memory.
3. Optionally back up the source to `BACKUP_DIR`.
4. Copy the source with `shutil.copy2` to a temp file in the target directory.
5. Modify tags in the temp file with Mutagen.
6. Atomically move the temp file to the target name.
7. During a pass, clean up old backups according to `BACKUP_RETENTION_DAYS`
   (at most hourly in loop mode).

Same-directory mode:

- Target name: `<basename> <suffix>.m4b`
- Example: `book [TAGS_REMAPPED].m4b`
- The source remains unchanged as long as `OVERWRITE_SOURCE_FILE=false`.
- With `OVERWRITE_SOURCE_FILE=true`, the source is overwritten in place; a backup
  is strongly recommended but not mandatory.
- `OUTPUT_SUFFIX=true` takes precedence and creates a copy with the suffix even
  when source overwrite is allowed.
- Files that already carry the suffix are skipped when `SKIP_SUFFIX=true`.
- Existing target files are skipped when `OVERWRITE_EXISTING=false`.

Suffix rules:

- `OUTPUT_SUFFIX=true`: the suffix is always appended (idempotent).
- `OUTPUT_SUFFIX=false`: the suffix is appended only when the target path would
  otherwise be identical to the source and `OVERWRITE_SOURCE_FILE=false`.
- Replicate/recursive mode does not append a suffix unless `OUTPUT_SUFFIX` is set.
- An empty `RENAME_SUFFIX` is allowed in same-directory mode only with
  `OVERWRITE_SOURCE_FILE=true`.

### 2.2 Configuration

Supported:

- environment variables
- `.env` (also for direct Python invocation)
- YAML (`CONFIG_FILE` / `--config`)
- CLI arguments
- single file as a positional argument

Precedence: defaults < YAML < `.env`/environment < CLI.

Important variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `INPUT_DIR` | `/in` | Input directory |
| `OUTPUT_DIR` | `/out` | Output directory |
| `FILENAME_FILTER` | `*.m4b` | File name filter |
| `TAG_MAP` | – | JSON list of tag-to-tag mappings |
| `TAG_RULES` | – | JSON list of value replacements |
| `RECURSIVE` | `false` | Include subdirectories |
| `REPLICATE_SOURCE_DIR_STRUCTURE` | `false` | Search recursively and mirror source structure under `OUTPUT_DIR` |
| `OUTPUT_SUFFIX` | `false` | Always append `RENAME_SUFFIX` to output files |
| `OVERWRITE_EXISTING` | `false` | Overwrite existing output |
| `OVERWRITE_SOURCE_FILE` | `false` | Overwrite source in place; backup strongly recommended |
| `OUTPUT_SAME_DIR` | `false` | Put the copy in the source folder |
| `RENAME_SUFFIX` | `[TAGS_REMAPPED]` | Suffix text for output files |
| `SKIP_SUFFIX` | `true` | Skip files that already carry the suffix |
| `BACKUP` | `false` | Back up the input file before processing |
| `BACKUP_DIR` | – | Backup target; required when `BACKUP=true` |
| `BACKUP_RETENTION_DAYS` | `30` | Delete backups older than N days; `0` disables |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOOP` | `false` | Continuous operation (Compose: `true`) |
| `LOOP_INTERVAL` | `60` | Seconds between loop passes |
| `SINGLE_FILE` | – | Process exactly one file |
| `CONFIG_FILE` | – | Path to YAML configuration |
| `ENV_FILE` | `.env` | Path to `.env` |

### 2.3 Default Mapping

Without `TAG_MAP` and without `TAG_RULES`:

| Source | Target | Written MP4 atoms |
| --- | --- | --- |
| `album` | `series` | `tvsh` + `mvnm` |
| `track` | `series-part` | `tven` + `mvin` (integer) |
| `title` | `album` | `©alb` |

Mappings run before value replacements. Explicit `TAG_MAP` entries completely
replace the default mapping.

### 2.4 Supported Logical Tags

`album`, `artist`, `title`, `albumartist`, `track`, `year`, `genre`, `composer`,
`comment`, `grouping`, `description`, `subtitle`, `publisher`, `series`,
`series-part`, `language`, `isbn`, `asin`.

Aliases: `album-artist`/`album_artist`, `author`, `narrator`, `mvnm`/`show`,
`mvin`/`episode_id`, `series_part`, `lang`, `audible_asin`/`audible-asin`.

### 2.5 Docker

`compose.yml` (not `docker-compose.yml`):

- One file with `build: .` and
  `image: ghcr.io/yasuoiwakura/audiobook-tag-rewriter:${IMAGE_TAG:-latest}`
- `docker compose up --build` builds locally
- `docker compose pull && docker compose up --no-build` uses the GHCR image
- Compose service with loop (`LOOP=true`, `LOOP_INTERVAL=60`)
- `restart: on-failure`
- `HOST_INPUT_DIR` (default `./m4b_from_AudioBookConverter`) → `/data/in`
  (read-only, input)
- `HOST_OUTPUT_DIR` (default `./m4b_for_AudioBookShelf`) → `/data/out`
  (read-write, output)
- `HOST_BACKUP_DIR` (default `./m4b_backup`) → `/data/backup` (read-write,
  backup)
- `HOST_CONFIG_DIR` (default `./config`) → `/config` (read-only, optional YAML)
- Container runs as non-root (UID 1000)

Environment order via `env_file`:

1. `upstream.env` (committed defaults)
2. `override.env` (optional, ignored)
3. `.env` (optional, ignored)

Later files override earlier values. `upstream.env` sets `BACKUP=true`.
`BACKUP=false` in `override.env` or `.env` disables the backup.

`HOST_*`, `IMAGE_TAG`, and other Compose interpolation variables are not read from
`env_file`. They come from the shell or `.env`; without `.env`, the defaults in
`compose.yml` apply. `.env` remains optional.

There is also a standalone example stack in
[`examples/abs/`](examples/abs/README.md). It starts the fixer and Audiobookshelf
together; the fixer writes to `data/out`, which ABS mounts as `/audiobooks`.
The example stack uses its own `upstream.env`/`override.env` files and sets
`REPLICATE_SOURCE_DIR_STRUCTURE=true` to preserve the ABS structure with one
folder per book.

`OUTPUT_SAME_DIR=true` requires a writable source directory. The default Compose
setup mounts `/data/in` read-only; same-directory mode requires adjusting the
mount.

Logging:

- Each file name is logged once.
- All relevant read or written tags appear in the table
  `Tag | Old Value | New Value`, including unchanged and read-only tags; empty
  values use the current CLI marker `<leer>`.
- Times are printed for backup, copy, tags, target rename, and total.
- Empty or skip-only loop passes are logged only at `DEBUG`.
- `LOG_LEVEL=INFO` is quiet while idle; `WARNING`/`ERROR` reduce output further.

### 2.6 Verification

- `pytest`: 131 tests passed
- `ruff check src tests`: passed
- `docker compose config`: validated successfully
- `docker compose -f examples/abs/compose.yml config`: validated successfully
- Docker build/container start: **not verified**, because the Docker daemon was
  not running in the development environment

## 3. Series Mapping

### 3.1 Written Atoms

| Logical | MP4 atoms | ffprobe key without `-export_all` | ABS mapping |
| --- | --- | --- | --- |
| `series` | `tvsh`, `mvnm` | `show` | Series |
| `series-part` | `tven`, `mvin` | `episode_id` | Series Sequence |

`tven` is written as text; `mvin` as a real MP4 integer atom.

When reading, `tvsh`/`tven` take precedence. If they are missing, `mvnm`/`mvin`
are read. This keeps older output files compatible.

### 3.2 Why Also Write tvsh/tven?

- ABS invokes ffprobe without `-export_all`.
- For MP4/M4B, `mvnm`/`mvin` are unknown atoms to ffprobe and only appear with
  `-export_all`.
- `tvsh`/`tven` are returned by ffprobe as `show`/`episode_id` and are already
  mapped by ABS to Series/Series Sequence.
- `mvnm`/`mvin` are written additionally so other players can find them.

### 3.3 Verification

Synthetic M4B file after mapping:

```text
without -export_all:  show = Old Album, episode_id = 3
with -export_all:     additionally mvnm = Old Album, mvin = 3
```

This provides the ffprobe path ABS expects via `show`/`episode_id`; an actual ABS
scan was not executed in this environment.

## 4. Known Limitations

1. **Always a full copy:** Even unchanged files are copied. For an 834 MB file,
   about 73 seconds were measured (copy plus `mdat` shift by Mutagen).
2. **MP4 layout:** When `moov` precedes `mdat`, every tag growth shifts the `mdat`
   block. This is not a copy problem but a property of the MP4 layout and Mutagen.
3. **No move mode:** Source files are neither moved nor deleted. In-place
   overwrite is possible via `OVERWRITE_SOURCE_FILE=true`, but it is not
   idempotent in loop mode.
4. **Backup costs storage/time:** `BACKUP=true` copies the input file in full to
   `BACKUP_DIR`. Old backups are cleaned up according to `BACKUP_RETENTION_DAYS`.
5. **Docker build/container start** were not executed in this environment;
   `docker compose config` is validated.
6. **Same-directory mode in a container** requires a writable `/data/in` mount.

## 5. Optional Next Steps

Not implemented, only noted:

- `MODE=move`: in-place editing plus native rename, fallback copy+delete
- Reflink/CoW copy when the file system supports it
- Layout analysis/warning before a large `mdat` shift
- Additional metadata fields or freeform-based series tags

## 6. Acceptance Criteria

Met:

1. `series` is written as `tvsh` and `mvnm`.
2. `series-part` is written as `tven` and `mvin`.
3. ffprobe without `-export_all` shows `show` and `episode_id`.
4. Same-directory mode creates `<basename> [TAGS_REMAPPED].m4b`.
5. The source hash remains identical before and after processing.
6. Tests and Ruff pass.
7. README, `.env.example`, `upstream.env`, `override.env.example`, and
   `config.example.yml` are up to date.
8. `compose.yml` uses multiple env files and the three data mounts.
9. The GHCR workflow builds and pushes the image.
10. `compose.yml` supports local builds and the prebuilt image without an
    additional Compose file.
11. Documentation is structured across `README.md`, `doc/PROBLEM.md`,
    `doc/ARCHITECTURE.md`, `doc/CONFIGURATION.md`, `doc/OPERATIONS.md`, and
    `CONTRIBUTING.md`, with cross-links.
12. `examples/abs/` provides a valid Compose stack with the fixer and
    Audiobookshelf; `data/out` is the ABS library and `data/in` remains
    read-only.
13. The frozen German README snapshot is archived at
    [`doc/archive/README.de.md`](doc/archive/README.de.md) and linked from
    `README.md`; it is not maintained.

## 7. References

- AudioBookConverter Issue #759: metadata mapping for Audiobookshelf
  <https://github.com/yermak/AudioBookConverter/issues/759>
- Audiobookshelf Issue #5669: separate mapping for M4B
  <https://github.com/advplyr/audiobookshelf/issues/5669>
- Audiobookshelf Issue #2471: movementname/movement vs. mvnm/mvin
  <https://github.com/advplyr/audiobookshelf/issues/2471>
- Audiobookshelf documentation “Book Library Structure”
  <https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/>
- ABS sources:
  - `server/libs/nodeFfprobe/index.js`
  - `server/utils/prober.js`
  - `server/scanner/AudioFileScanner.js`
- Upstream issue draft for the ABS repository:
  [`ABS-issue-readtags.md`](ABS-issue-readtags.md)
- Project problem and decision: [`doc/PROBLEM.md`](doc/PROBLEM.md)
- Technical flow: [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md)
- All options: [`doc/CONFIGURATION.md`](doc/CONFIGURATION.md)
- Operations and troubleshooting: [`doc/OPERATIONS.md`](doc/OPERATIONS.md)
- Fixer + ABS as a stack: [`examples/abs/`](examples/abs/README.md)
