# feat-0006 – Complete Tag Report

Status: planned<br>
Target variant: `m4b-tag-fixer`<br>
Default: `TAG_REPORT=all` (proposed)

## 1. Goal

Log a complete per-file tag report instead of only the tags that changed.

Today the `INFO` table (`Tag | Old Value | New Value`) contains only mappings that
were applied. Everything else is invisible or only available at `DEBUG`:

- tags that were read but not written
- tags that already had the desired value (unchanged mappings)
- tags touched by `TAG_RULES` that did not match
- all other supported tags of the source file

Requirement: every tag that is **read or written** should appear in the output,
with its value before and after processing. This makes it possible to verify a
file's full metadata state from the log without enabling `DEBUG`.

## 2. Current Behavior

Example from a default-mapping run:

```text
Tag         | Old Value   | New Value
------------+-------------+--------------------------------
series      | <leer>      | Elder Races
series-part | <leer>      | 1
album       | Elder Races | Im Bann des Drachen (ungekürzt)
```

`title`, `artist`, `composer`, `track`, and all unchanged values are missing, even
though they were read from the source. The source file may also contain tags
(`comment`, `grouping`, ...) that never appear at all.

## 3. Configuration

New option. It can be set through every existing configuration path:

| Path | Syntax |
| --- | --- |
| Environment / `.env` | `TAG_REPORT=all` or `TAG_REPORT=changes` |
| YAML | `tag_report: all` |
| CLI | `--tag-report all` / `--tag-report changes` |

Values:

| Value | Meaning |
| --- | --- |
| `all` | Complete report with all read/written tags (new default) |
| `changes` | Previous behavior: only changed tags |

Invalid values cause a configuration error (exit code 2). Precedence as before:
defaults < YAML < `.env`/environment < CLI.

## 4. Behavior

### 4.1 Which Tags Are Listed

A tag is included when at least one of these is true:

- it had a value in the source snapshot (read)
- it has a value after mappings/rules (written or would be written)
- it is the source or target of a configured `TAG_MAP` entry
- it is the tag of a configured `TAG_RULES` entry

Tags that are neither set nor referenced by configuration are omitted, so the
report stays readable. With `TAG_REPORT=all`, all supported tags are available via
`LOG_LEVEL=DEBUG` (raw atom level) for deep diagnosis.

Ordering follows the existing display order (`album`, `title`, `artist`, ..., see
`DISPLAY_FIELDS`); remaining tags follow alphabetically.

### 4.2 Columns

| Column | Content |
| --- | --- |
| `Tag` | Logical tag name (for example `series`, `series-part`) |
| `Old Value` | Value from the source snapshot before any change |
| `New Value` | Value after all mappings and rules |
| `State` | `changed`, `unchanged`, `read`, or `written` |

State definitions:

- `changed`: old and new differ.
- `unchanged`: mapping/rule touched the tag but the resulting value equals the old
  value, or the target already had the desired value.
- `read`: the tag was read but is not part of any mapping/rule.
- `written`: the tag is a mapping target or rule tag that received a value.

If a fourth column is undesirable, the state can be folded into the existing
three-column table (open implementation detail). The values themselves are
mandatory.

### 4.3 Values

- Multiple values are joined with `, ` (as today).
- Empty values use the existing `<leer>` marker.
- `\r` and `\n` are escaped as `\r` and `\n` (as today).
- The report uses logical tags, not raw MP4 atoms. Atom-level details
  (`tvsh`/`mvnm`, `tven`/`mvin`) remain a `DEBUG` concern.

### 4.4 Logging

- The report is logged at `INFO` for every processed file, including files without
  changes.
- `TAG_REPORT=changes` keeps the current table and the current
  `Keine Tag-Änderungen.` line.
- With `TAG_REPORT=all`, the `Keine Tag-Änderungen.` line is replaced by the full
  report.
- The report is based on the in-memory snapshot before and after mappings/rules;
  the written file itself is not re-read.
- Summary counters (`Erfolgreiche Tag-Änderungen` etc.) remain unchanged and count
  actual changes, not reported rows.

### 4.5 Example

```text
  Tag         | Old Value                   | New Value                   | State
  ------------+-----------------------------+-----------------------------+----------
  album       | Elder Races                 | Im Bann des Drachen         | changed
  title       | Im Bann des Drachen         | Im Bann des Drachen         | read
  artist      | Thea Harrison               | Thea Harrison               | read
  composer    | Tanja Fornaro               | Tanja Fornaro               | read
  track       | 1                           | 1                           | read
  series      | <leer>                      | Elder Races                 | changed
  series-part | <leer>                      | 1                           | changed
```

## 5. Acceptance Criteria

1. `TAG_REPORT=all` lists every tag that is read or written for the file.
2. Unchanged mappings and unmatched `TAG_RULES` appear with their values.
3. Tags that were only read (for example `artist`, `composer`) appear.
4. `TAG_REPORT=changes` reproduces the previous table exactly.
5. Empty values still use `<leer>`; multi-values and newlines are formatted as
   before.
6. Invalid `TAG_REPORT` values produce a configuration error (exit code 2).
7. The report does not change processing, writing, or summary counters.
8. Default behavior matches the requested full report.
9. Existing tests for the change table are updated; new tests cover `all` and
   `changes`.

## 6. Tests

- Config: default `all`, env/YAML/CLI parsing, CLI overrides YAML, invalid value.
- Processor: full report contains changed, unchanged, read-only, and rule tags.
- Processor: `changes` keeps the old three-column change table.
- Processor: file without changes still prints the full report under `all`.
- Processor: `<leer>`, multi-value, and newline formatting.
- Regression: summary counts and written output stay identical.

## 7. Documentation

- `README.md` (variable table, logging section)
- `SPEC.md` (variable table, logging section)
- `.env.example`, `override.env.example`, `upstream.env`
- `config.example.yml`
- `doc/CONFIGURATION.md` and `doc/OPERATIONS.md` (logging example)
- `doc/FEATURES/README.md` (inventory)

## 8. Open Questions

- Should `all` or `changes` be the default? This document proposes `all` because
  the current gap is the reported problem.
- Should the state be a fourth column or an inline marker?
- Should an additional summary table (all files) be added later, or is the
  per-file report sufficient?
