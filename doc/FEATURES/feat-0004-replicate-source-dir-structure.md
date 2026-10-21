# feat-0004 – Mirror Source Directory Structure

Status: implemented<br>
Target variant: `m4b-tag-fixer`<br>
Default: `false` (disabled)

## 1. Goal

Optionally mirror the source directory structure in the output directory. To do
this, files are found recursively in the source directory and the output file is
placed in the corresponding subdirectory.

Example:

```text
/data/in/German/audiobook.m4b
  -> /data/out/German/audiobook.m4b
```

The subdirectory `German` is therefore preserved. The file is still only copied
and modified; the source remains unchanged. This feature does not change the file
name; see `feat-0005` for suffix behavior.

## 2. Configuration

New option, disabled by default. It can be set through every existing
configuration path:

| Path | Syntax |
| --- | --- |
| Environment / `.env` | `REPLICATE_SOURCE_DIR_STRUCTURE=true` |
| YAML | `replicate_source_dir_structure: true` |
| CLI | `--replicate-source-dir-structure` / `--no-replicate-source-dir-structure` |

Precedence as before: defaults < YAML < `.env`/environment < CLI.

Boolean values follow the existing logic (`true/false`, `1/0`, `yes/no`,
`on/off`, `ja/nein`).

## 3. Behavior

### 3.1 File Discovery

- `REPLICATE_SOURCE_DIR_STRUCTURE=true` implies recursive search (`RECURSIVE` does
  not need to be set separately).
- `FILENAME_FILTER`, the `.m4b` check, and `SKIP_SUFFIX` still apply.
- Sorting remains stable and case-insensitive.

### 3.2 Output Path

- The relative path of the source file to `INPUT_DIR` is mirrored under
  `OUTPUT_DIR`.
- Missing subdirectories are created automatically.
- The file name remains unchanged. `OUTPUT_SUFFIX` and `OVERWRITE_SOURCE_FILE` are
  independent of this feature (see `feat-0005`).

Examples:

| `INPUT_DIR` | Source file | `OUTPUT_DIR` | Result |
| --- | --- | --- | --- |
| `/data/in` | `/data/in/German/audiobook.m4b` | `/data/out` | `/data/out/German/audiobook.m4b` |
| `/data/in` | `/data/in/a/b/book.m4b` | `/data/out` | `/data/out/a/b/book.m4b` |
| `/data/in` | `/data/in/book.m4b` | `/data/out` | `/data/out/book.m4b` |

### 3.3 Interaction with Existing Options

- `OUTPUT_SAME_DIR=true` takes precedence: the copy still goes next to the source.
- `SINGLE_FILE` takes precedence: an explicitly provided single file is written
  flat to `OUTPUT_DIR`.
- `RECURSIVE=true` without `REPLICATE_SOURCE_DIR_STRUCTURE` keeps the previous
  behavior (recursive search, structure in the target, file name without an
  additional suffix).
- `RECURSIVE=true` together with `REPLICATE_SOURCE_DIR_STRUCTURE=true` is the same
  behavior; `RECURSIVE` is then redundant.
- `OUTPUT_SUFFIX`, `OVERWRITE_SOURCE_FILE`, `OVERWRITE_EXISTING`, and `SKIP_SUFFIX`
  apply unchanged.

### 3.4 Validation

- When enabled, `OUTPUT_DIR` must not be inside `INPUT_DIR` (analogous to
  `RECURSIVE=true`).
- When enabled with `BACKUP=true`, `BACKUP_DIR` must not be inside `INPUT_DIR`.
- Invalid boolean values cause a `ConfigError` naming the variable.

### 3.5 Logging

- At startup, the active state is logged.
- For each file, the actual output path is still logged.

## 4. Acceptance Criteria

1. The default is `false`; without enabling it, existing behavior is unchanged.
2. `REPLICATE_SOURCE_DIR_STRUCTURE=true` finds `.m4b` files in subdirectories.
3. The output file is placed in the mirrored subdirectory under `OUTPUT_DIR`.
4. The file name remains unchanged without `OUTPUT_SUFFIX`.
5. The source remains byte-identical.
6. `--no-replicate-source-dir-structure` overrides `true` from env/YAML.
7. Invalid values and forbidden directory overlaps are rejected with a clear
   configuration error.

## 5. Tests

- Config: default `false`, env parsing, YAML key, CLI override, invalid value.
- Config: `OUTPUT_DIR`/`BACKUP_DIR` inside `INPUT_DIR` is rejected.
- Processor: a flat directory is mirrored.
- Processor: multiple levels (`a/b/book.m4b`) are mirrored.
- Processor: file name remains unchanged without `OUTPUT_SUFFIX`.
- Processor: `OUTPUT_SUFFIX=true` appends the suffix.
- Processor: an existing target is skipped or overwritten according to
  `OVERWRITE_EXISTING`.
- Regression: `RECURSIVE=true` without the new option behaves as before.

## 6. Documentation

- `README.md` (variable table, directory-structure section, CLI example)
- `SPEC.md` (implementation status, variable table)
- `.env.example`, `override.env.example`, `upstream.env`
- `config.example.yml`
- `doc/CONFIGURATION.md` and `doc/OPERATIONS.md`
- `doc/FEATURES/feat-0005-output-suffix-and-overwrite-source.md`
