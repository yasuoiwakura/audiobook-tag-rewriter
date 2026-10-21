# Configuration

## 1. Precedence

There are four layers. Later sources override earlier ones:

1. built-in defaults
2. YAML file (`CONFIG_FILE` or `--config`)
3. `.env` / process environment variables
4. command-line arguments

When invoked directly with Python, `.env` is loaded from the current working
directory. Existing process variables take precedence. Alternatively, use
`--env-file` or `ENV_FILE`.

## 2. Environment Variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `INPUT_DIR` | `/in` | Input directory (not required for a single file) |
| `OUTPUT_DIR` | `/out` | Output directory |
| `FILENAME_FILTER` | `*.m4b` | Glob pattern for file names |
| `TAG_MAP` | – | JSON list of tag mappings |
| `TAG_RULES` | – | JSON list of value replacements |
| `RECURSIVE` | `false` | Include subdirectories and mirror their structure |
| `REPLICATE_SOURCE_DIR_STRUCTURE` | `false` | Search recursively and mirror the source structure under `OUTPUT_DIR` |
| `OUTPUT_SUFFIX` | `false` | Always append `RENAME_SUFFIX` to output files |
| `OVERWRITE_EXISTING` | `false` | Overwrite existing output files |
| `OVERWRITE_SOURCE_FILE` | `false` | Overwrite the source in place; backup strongly recommended |
| `OUTPUT_SAME_DIR` | `false` | Put the copy in the source folder instead of `OUTPUT_DIR` |
| `RENAME_SUFFIX` | `[TAGS_REMAPPED]` | Suffix text for output files |
| `SKIP_SUFFIX` | `true` | Do not process files that already have this suffix |
| `BACKUP` | `false` | Back up the input file before processing |
| `BACKUP_DIR` | – | Backup target; required when `BACKUP=true` |
| `BACKUP_RETENTION_DAYS` | `30` | Delete backups older than N days; `0` disables cleanup |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, ... |
| `LOOP` | `false` | Continuous operation (Compose: `true`) |
| `LOOP_INTERVAL` | `60` | Seconds between loop passes; must be > 0 |
| `SINGLE_FILE` | – | Process exactly this `.m4b` file |
| `CONFIG_FILE` | – | Path to the optional YAML configuration |
| `ENV_FILE` | `.env` | Path to the `.env` file |

Boolean values: `true/false`, `1/0`, `yes/no`, `on/off`, `ja/nein`.

### Environment Files for Compose

The root `compose.yml` loads three files in this order:

1. `upstream.env` (committed defaults)
2. `override.env` (optional, ignored)
3. `.env` (optional, ignored)

Later files override earlier values. Compose interpolation with `${VAR}` reads
only `.env`; application configuration is passed through `env_file` instead.

```bash
cp override.env.example override.env   # optional
cp .env.example .env                   # optional
```

Host paths for mounts are Compose interpolation variables and belong in `.env`:

```dotenv
HOST_INPUT_DIR=./m4b_from_AudioBookConverter
HOST_OUTPUT_DIR=./m4b_for_AudioBookShelf
HOST_BACKUP_DIR=./m4b_backup
HOST_CONFIG_DIR=./config
```

## 3. File Name Filter

- The filter applies to the file name, not to subdirectories.
- Matching is case-insensitive; the extension must also be `.m4b`.
- By default, only files directly in `INPUT_DIR` are processed.
- `RECURSIVE=true` includes subdirectories and mirrors their structure under
  `OUTPUT_DIR`.
- `REPLICATE_SOURCE_DIR_STRUCTURE=true` searches `INPUT_DIR` recursively and
  mirrors subdirectories under `OUTPUT_DIR`; file names remain unchanged.
  `RECURSIVE` does not need to be set separately.
- Files whose base name already ends with `RENAME_SUFFIX` are not processed again
  when `SKIP_SUFFIX=true`.

Example:

```text
INPUT_DIR/German/book.m4b -> OUTPUT_DIR/German/book.m4b
```

## 4. Suffix and Overwrite Behavior

> **Warning:** `OVERWRITE_SOURCE_FILE=true` overwrites the source file
> irreversibly. `BACKUP=true` is strongly recommended. Without a backup,
> processing still runs, but logs a warning for each file.

- `OUTPUT_SUFFIX=false` (default): The suffix is appended only as a safety net
  when the target path would otherwise be identical to the source and
  `OVERWRITE_SOURCE_FILE=false`.
- `OUTPUT_SUFFIX=true`: The suffix is always appended (not twice if it is already
  part of the name).
- `OUTPUT_SAME_DIR=true`: The target path is the source itself. Without
  `OVERWRITE_SOURCE_FILE=true`, the suffix is therefore appended automatically.
- `OVERWRITE_SOURCE_FILE=true`: The source is overwritten in place.
  `BACKUP=true` is strongly recommended. `OUTPUT_SUFFIX=true` takes precedence
  and creates a copy with the suffix instead; the source remains unchanged.
- An empty `RENAME_SUFFIX` is allowed in same-directory mode only with
  `OVERWRITE_SOURCE_FILE=true`.
- `OUTPUT_DIR` and `INPUT_DIR` must not be identical.

| Target mode | `OUTPUT_SUFFIX` | `OVERWRITE_SOURCE_FILE` | Result |
| --- | --- | --- | --- |
| Replicate/recursive | `false` | any | `out/German/book.m4b` |
| Replicate/recursive | `true` | any | `out/German/book [TAGS_REMAPPED].m4b` |
| Same-directory | `false` | `false` | `book [TAGS_REMAPPED].m4b` (safety net) |
| Same-directory | `false` | `true` | Source is overwritten in place |
| Same-directory | `true` | any | `book [TAGS_REMAPPED].m4b` (explicit) |
| Flat | `false` | any | `out/book.m4b` |
| Flat | `true` | any | `out/book [TAGS_REMAPPED].m4b` |

In loop mode, an in-place processed file is processed again on every pass. For a
permanent input folder, separate-output mode is therefore the better choice.

## 5. TAG_MAP (Tag-to-Tag Mapping)

`TAG_MAP` is a JSON list. Each entry requires `from` and `to` (alternatively
`source` and `target`).

```json
[
  {"from": "album", "to": "series"},
  {"from": "track", "to": "series-part"},
  {"from": "title", "to": "album"}
]
```

- If a mapping is provided, it completely replaces the default mapping.
- `TAG_MAP=[]` disables the default mapping.
- Mappings run in order; each rule reads the current intermediate state. Chains
  are therefore possible.
- If the source is missing, the entry is logged and skipped.
- On success, the target is overwritten; the previous target value is logged.
- `series-part`/`mvin` expects an integer.
- Unknown tags, missing required fields, and invalid JSON cause exit code 2.

### Default Mapping

Without `TAG_MAP` and without `TAG_RULES`:

| Source | Target | MP4 atoms |
| --- | --- | --- |
| `album` | `series` | `tvsh` + `mvnm` |
| `track` | `series-part` | `tven` + `mvin` (integer) |
| `title` | `album` | `©alb` |

Mappings **copy** values; the source remains. `title -> album` therefore
intentionally overwrites the previous album after it has been copied to `series`.

Only `TAG_RULES` set? Then **no** default mapping applies, because an explicit
change instruction is present. Mappings always run before value replacements.

## 6. TAG_RULES (Value Replacements)

`TAG_RULES` replaces existing values exactly. There is no substring replacement.

```json
[
  {"tag": "album", "old": "Old Album", "new": "New Album"},
  {"tag": "artist", "old": "Old Author", "new": "New Author"},
  {"tag": "track", "old": "3", "new": "7"}
]
```

- Rules run after all mappings, in the specified order.
- Only exact matches are replaced (case-sensitive).
- Multi-value fields: only exactly matching values are replaced; others remain.
- Missing tags and non-matching values are not errors, but are logged.
- `track` is read/compared without leading zeros; the total track count remains.
- Invalid JSON, missing required fields, unknown tags, identical `old`/`new`, and
  non-numeric track values cause exit code 2.
- `TAG_RULES=[]` allows a run without value replacements (and, together with a
  missing `TAG_MAP`, disables the default mapping).

## 7. Supported Tags

| Rule name | MP4 atom | Note |
| --- | --- | --- |
| `album` | `©alb` | Album |
| `artist` | `©ART` | Artist / author |
| `title` | `©nam` | Title |
| `albumartist` | `aART` | Album artist |
| `track` | `trkn` | Track number; total count is preserved |
| `year` | `©day` | Year / date |
| `genre` | `©gen` | Genre |
| `composer` | `©wrt` | Composer / often narrator for audiobooks |
| `comment` | `©cmt` | Comment |
| `grouping` | `©grp` | Grouping |
| `description` | `desc` | Description |
| `subtitle` | `©st3` | Subtitle |
| `publisher` | `©pub` | Publisher |
| `series` | `tvsh` + `mvnm` | Series; `tvsh` = ABS/ffprobe `show` |
| `series-part` | `tven` + `mvin` | Series sequence; `tven` = `episode_id`, `mvin` = integer |
| `language` | `lang` | Language |
| `isbn` | `----:com.apple.iTunes:ISBN` | Freeform |
| `asin` | `----:com.apple.iTunes:ASIN` | Freeform |

Aliases:

- `album-artist`, `album_artist` → `albumartist`
- `author` → `artist`
- `narrator` → `composer`
- `mvnm`/`show` → `series`
- `mvin`/`episode_id`/`series_part` → `series-part`
- `lang` → `language`
- `audible_asin`, `audible-asin` → `asin`

`mvin` is written as a real MP4 integer atom, `tven` as text. When reading,
`tvsh`/`tven` take precedence over `mvnm`/`mvin`. Cover (`covr`), chapters
(`chpl`), and other existing atoms are preserved when writing.

## 8. YAML Configuration

Enable with `--config` or `CONFIG_FILE`.

```yaml
input_dir: /data/in
output_dir: /data/out
backup_dir: /data/backup
backup: true
filename_filter: "*.m4b"
recursive: false
replicate_source_dir_structure: false
output_suffix: false
overwrite_source_file: false
overwrite_existing: false
log_level: INFO
loop: false
loop_interval: 60

tag_map:
  - from: album
    to: series
  - from: track
    to: series-part
  - from: title
    to: album

# optional, in addition to the mapping:
# tag_rules:
#   - tag: album
#     old: Old Album
#     new: New Album
```

A complete template is included as `config.example.yml`. For Docker:

```bash
mkdir -p config
cp config.example.yml config/config.yml
```

and in `.env`:

```dotenv
CONFIG_FILE=/config/config.yml
```

## 9. CLI

```bash
python -m m4b_tag_fixer --input-dir ./in --output-dir ./out
python -m m4b_tag_fixer --tag-map '[{"from":"album","to":"series"}]'
python -m m4b_tag_fixer --no-loop --log-level DEBUG
python -m m4b_tag_fixer --config config.example.yml --no-loop
python -m m4b_tag_fixer --input-dir ./in --output-dir ./out --recursive
python -m m4b_tag_fixer --input-dir ./in --output-dir ./out --replicate-source-dir-structure
python -m m4b_tag_fixer --input-dir ./in --output-dir ./out --replicate-source-dir-structure --output-suffix
python -m m4b_tag_fixer --input-dir ./in --same-dir --overwrite-source-file --backup --backup-dir ./backup
python -m m4b_tag_fixer --input-dir ./in --same-dir --rename-suffix "[TAGS_REMAPPED]"
```

`PYTHONPATH=src` is required if the package has not been installed. `run.bat`
sets it automatically.

## 10. Validation

Exit code `2` on configuration errors, including:

- `INPUT_DIR` does not exist or is not a directory.
- `INPUT_DIR == OUTPUT_DIR`.
- `OUTPUT_DIR` is inside `INPUT_DIR` during recursive processing.
- `BACKUP=true` without `BACKUP_DIR`.
- `BACKUP_DIR` is identical to `INPUT_DIR` or `OUTPUT_DIR`.
- `BACKUP_DIR` is inside `INPUT_DIR` during recursive processing.
- Invalid boolean, numeric, or JSON values.
- Unknown YAML keys or tags.
- `RENAME_SUFFIX` contains invalid file name characters.
- Same-directory mode with an empty suffix and without
  `OVERWRITE_SOURCE_FILE=true`.

## 11. Further Reading

- [`OPERATIONS.md`](OPERATIONS.md) – Docker, backup, and troubleshooting
- [`ARCHITECTURE.md`](ARCHITECTURE.md) – technical flow
- [`PROBLEM.md`](PROBLEM.md) – why the mapping is necessary
