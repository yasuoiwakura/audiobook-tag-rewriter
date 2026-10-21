# feat-0005 – Output Suffix and Source Overwrite

Status: implemented<br>
Target variant: `m4b-tag-fixer`<br>
Defaults: `OUTPUT_SUFFIX=false`, `OVERWRITE_SOURCE_FILE=false`

## 1. Goal

Decouple suffix behavior and source overwriting from the directory structure:

- `OUTPUT_SUFFIX` controls only whether `RENAME_SUFFIX` is appended to output
  files.
- `OVERWRITE_SOURCE_FILE` allows overwriting the source in place.
- Without overwrite permission, the suffix is appended automatically only when the
  target path would otherwise be identical to the source.

`REPLICATE_SOURCE_DIR_STRUCTURE=true` does **not** imply `OUTPUT_SUFFIX=true`.

## 2. Configuration

| Path | `OUTPUT_SUFFIX` | `OVERWRITE_SOURCE_FILE` |
| --- | --- | --- |
| Environment / `.env` | `OUTPUT_SUFFIX=true` | `OVERWRITE_SOURCE_FILE=true` |
| YAML | `output_suffix: true` | `overwrite_source_file: true` |
| CLI | `--output-suffix` / `--no-output-suffix` | `--overwrite-source-file` / `--no-overwrite-source-file` |

`RENAME_SUFFIX` remains the suffix text (default `[TAGS_REMAPPED]`).

Precedence as before: defaults < YAML < `.env`/environment < CLI.

## 3. Behavior

### 3.1 Target Path

```text
base = target path without suffix
       same-dir   -> source
       replicate  -> OUTPUT_DIR / relative(source, INPUT_DIR)
       flat       -> OUTPUT_DIR / source.name

target = base
if OUTPUT_SUFFIX:
    target = with_suffix(base)                    # always
elif base == source and not OVERWRITE_SOURCE_FILE:
    target = with_suffix(base)                    # overwrite protection
```

`with_suffix` does not append the suffix twice if the base name already ends with
it.

### 3.2 Matrix

| Mode | `OUTPUT_SUFFIX` | `OVERWRITE_SOURCE_FILE` | Result |
| --- | --- | --- | --- |
| Same-directory | `false` | `false` | `book [TAGS_REMAPPED].m4b` |
| Same-directory | `false` | `true` | Source is overwritten in place |
| Same-directory | `true` | any | `book [TAGS_REMAPPED].m4b`, source unchanged |
| Replicate/recursive | `false` | any | `out/sub/book.m4b` |
| Replicate/recursive | `true` | any | `out/sub/book [TAGS_REMAPPED].m4b` |
| Flat | `false` | any | `out/book.m4b` |
| Flat | `true` | any | `out/book [TAGS_REMAPPED].m4b` |

### 3.3 In-Place Overwrite

- Only when `target == source` and `OVERWRITE_SOURCE_FILE=true`.
- `OUTPUT_SUFFIX=true` takes precedence: a copy with the suffix is created, and the
  source remains unchanged.
- `BACKUP=true` is strongly recommended. Without a backup, processing still runs;
  a warning is logged per file and nothing is backed up.
- The source file is backed up first, read, and atomically replaced via a temp file
  in the source directory.
- In loop mode, an in-place processed file is processed again on every pass.

### 3.4 Validation

- `OVERWRITE_SOURCE_FILE=true` without `BACKUP=true` is allowed but logs a clear
  warning at startup and per affected file.
- `OUTPUT_SAME_DIR=true` with an empty `RENAME_SUFFIX` is allowed only with
  `OVERWRITE_SOURCE_FILE=true`.
- An empty suffix with forced overwrite protection (target == source, overwrite not
  allowed) causes a file error.
- `OUTPUT_DIR == INPUT_DIR` remains forbidden.

### 3.5 Logging

- At startup, suffix application, suffix text, and source-overwrite state are
  logged.
- The actual `RECURSIVE` value and the effective recursive-search state
  (including replicate) are logged separately.
- In-place overwrites are logged as warnings per file.

## 4. Acceptance Criteria

1. `OUTPUT_SUFFIX=true` appends the suffix in every mode.
2. `OUTPUT_SUFFIX=false` appends the suffix only when the target path would
   otherwise be identical.
3. Replicate mode does not append a suffix without `OUTPUT_SUFFIX`.
4. Same-directory mode appends the suffix automatically without overwrite
   permission.
5. `OVERWRITE_SOURCE_FILE=true` overwrites the source in place and creates a
   backup first.
6. Without a backup, in-place mode is allowed but logs a clear warning at startup
   and per file.
7. `OUTPUT_SUFFIX=true` creates a copy even when overwrite is allowed.

## 5. Tests

- Config: defaults, env/YAML/CLI parsing, `OVERWRITE_SOURCE_FILE` without backup
  allowed.
- Config: missing backup configuration produces a warning instead of an error.
- Config: same-directory mode with an empty suffix only with overwrite permission.
- Processor: same-directory in-place including backup.
- Processor: `OUTPUT_SUFFIX` wins over overwrite permission.
- Processor: in-place without backup works, changes the source, and logs a
  warning.
- Processor: replicate mode with and without `OUTPUT_SUFFIX`.
- Processor: a colliding flat target receives the suffix automatically.

## 6. Documentation

- `README.md` (variables, suffix/overwrite section, matrix, CLI)
- `SPEC.md` (implementation status, variables, suffix rules)
- `.env.example`, `override.env.example`, `upstream.env`
- `config.example.yml`
- `doc/CONFIGURATION.md` and `doc/OPERATIONS.md`
- `doc/FEATURES/README.md` (inventory)
