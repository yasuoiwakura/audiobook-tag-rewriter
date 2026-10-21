# Feature Inventory

Overview of planned, in-progress, and implemented features. Each feature has its
own document in this directory.

## Conventions

- Branch: `matt-nnnn`, sequential, for example `matt-0004`
- Feature file: `feat-nnnn-kebab-case-title.md`; `nnnn` matches the branch number
  (for example `feat-0004-replicate-source-dir-structure.md`)
- Document title: `# feat-nnnn – Title`
- Status values: `planned`, `in progress`, `implemented`, `discarded`
- Each document contains: goal, configuration, behavior, acceptance criteria,
  tests, documentation
- Implemented features are also listed in `SPEC.md`, `README.md`,
  `doc/CONFIGURATION.md`, and `doc/OPERATIONS.md`

## Inventory

| Feature | Branch | Status | Configuration | Summary |
| --- | --- | --- | --- | --- |
| [feat-0004](feat-0004-replicate-source-dir-structure.md) | `matt-0004` | implemented | `REPLICATE_SOURCE_DIR_STRUCTURE` (env, YAML, CLI) | Find files recursively and place them in the matching subdirectory under the output directory; default `false` |
| [feat-0005](feat-0005-output-suffix-and-overwrite-source.md) | `matt-0005` | implemented | `OUTPUT_SUFFIX`, `OVERWRITE_SOURCE_FILE` (env, YAML, CLI) | Apply the suffix explicitly or only as overwrite protection; optionally overwrite the source in place (`BACKUP=true` strongly recommended); defaults `false` |
| [feat-0006](feat-0006-complete-tag-report.md) | `matt-0006` | implemented | – | Extend the existing change table to every relevant tag that is read or written; no new configuration |
