# feat-0006 – Complete Tag Report

Status: implemented<br>
Target variant: `m4b-tag-fixer`<br>
Configuration: none

## 1. Goal

Log a complete per-file tag report instead of only the tags that changed.

The existing `INFO` table (`Tag | Old Value | New Value`) currently contains only
mappings that were applied. Tags that were read but not written, unchanged
mappings, and unmatched `TAG_RULES` are invisible.

Requirement: every relevant tag that is read or written should appear in the
existing table, with its value before and after processing.

## 2. Behavior

- The table is always logged at `INFO` for every processed file, including files
  without changes.
- The three existing columns remain unchanged: `Tag | Old Value | New Value`.
- No new option, environment variable, YAML key, or CLI flag is added.
- The report uses the in-memory snapshot before and after mappings/rules; the
  written file is not re-read.
- Summary counters remain unchanged and still count actual changes.

A tag is listed when at least one of these is true:

- it had a value in the source snapshot
- it has a value after mappings/rules
- it is the source or target of a configured `TAG_MAP` entry
- it is the tag of a configured `TAG_RULES` entry

Tags that are neither set nor referenced by the configuration are omitted, so the
table stays readable.

Ordering follows the existing display order (`album`, `title`, `artist`, ..., see
`DISPLAY_FIELDS`); remaining tags follow alphabetically.

### Values

- Multiple values are joined with `, ` (as before).
- Empty values use the existing `<leer>` marker.
- `\r` and `\n` are escaped as `\r` and `\n` (as before).
- Logical tags are shown, not raw MP4 atoms.

### Example

```text
  Tag         | Old Value             | New Value
  ------------+-----------------------+-----------------------------
  album       | Elder Races           | Im Bann des Drachen
  title       | Im Bann des Drachen   | Im Bann des Drachen
  artist      | Thea Harrison         | Thea Harrison
  composer    | Tanja Fornaro         | Tanja Fornaro
  track       | 1                     | 1
  series      | <leer>                | Elder Races
  series-part | <leer>                | 1
```

## 3. Acceptance Criteria

1. Every relevant tag that is read or written appears in the table.
2. Unchanged mappings and unmatched `TAG_RULES` appear with their values.
3. Tags that were only read (for example `artist`, `composer`) appear.
4. Files without changes still show the full report.
5. Empty values still use `<leer>`; multi-values and newlines are formatted as
   before.
6. No new configuration is introduced.
7. Processing, writing, and summary counters are unchanged.

## 4. Tests

- Processor: full report contains changed, unchanged, and read-only tags.
- Processor: file without changes still prints the full report.
- Processor: `<leer>`, multi-value, and newline formatting.
- Regression: summary counts and written output stay identical.

## 5. Documentation

- `SPEC.md` (logging section)
- `doc/OPERATIONS.md` (logging example)
- `doc/FEATURES/README.md` (inventory)
