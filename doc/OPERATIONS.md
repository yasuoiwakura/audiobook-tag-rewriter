# Operations

## 1. Requirements

- Docker with Docker Compose **≥ 2.24** (for `env_file.required`)
- Optional for local development: Python 3.12+ and `pip`
- For the ABS stack: the Audiobookshelf image `ghcr.io/advplyr/audiobookshelf`

## 2. Root Compose: Fixer Only

```bash
mkdir -p m4b_from_AudioBookConverter m4b_for_AudioBookShelf m4b_backup config
docker compose up --build
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force m4b_from_AudioBookConverter, m4b_for_AudioBookShelf, m4b_backup, config | Out-Null
docker compose up --build
```

The root `compose.yml` starts the fixer in loop mode. The input is read-only;
output and backup are read-write.

| Host (default / env) | Container | Access | Meaning |
| --- | --- | --- | --- |
| `./m4b_from_AudioBookConverter` / `HOST_INPUT_DIR` | `/data/in` | read-only | Input |
| `./m4b_for_AudioBookShelf` / `HOST_OUTPUT_DIR` | `/data/out` | read-write | Output / ABS library |
| `./m4b_backup` / `HOST_BACKUP_DIR` | `/data/backup` | read-write | Backup |
| `./config` / `HOST_CONFIG_DIR` | `/config` | read-only | Optional YAML |

Relative host paths are relative to the Compose file directory.

### Use a Prebuilt Image Instead of a Local Build

```bash
docker compose pull
docker compose up --no-build
```

`compose.yml` intentionally contains both `build: .` and `image:`. `--build`
builds locally; `pull` uses the published GHCR image. `IMAGE_TAG` defaults to
`latest`.

### Run Once Instead of in a Loop

```bash
LOOP=false docker compose up --build
```

PowerShell:

```powershell
$env:LOOP='false'; docker compose up --build
```

Run a single pass with an exit code for scripts:

```bash
docker compose run --rm -e LOOP=false m4b-tag-fixer
```

## 3. Loop Mode

- `LOOP=true`: The process stays active and scans every `LOOP_INTERVAL` seconds.
- Empty passes and skip-only passes are logged only at `DEBUG`.
- `INFO` shows only actual processing after startup.
- `SIGINT`/`SIGTERM` stop the loop cleanly with exit code 0.
- `restart: on-failure` restarts the container after a real failure.

## 4. Backup

- `BACKUP=true` copies the input file to `BACKUP_DIR` before processing.
- Relative paths are preserved.
- An identical existing backup is not copied again.
- If the backup fails, the file is not processed.
- A backup is a full file copy and costs time and storage.
- Old backups are deleted at the start of a pass according to
  `BACKUP_RETENTION_DAYS`; in loop mode at most once per hour.
- `0` disables cleanup.
- `BACKUP=true` requires `BACKUP_DIR`; otherwise exit code 2.

The root Compose setup sets `BACKUP=true` in `upstream.env`. `BACKUP=false` in
`override.env` or `.env` disables it.

## 5. Files, Overwriting, and Errors

- Source files are only modified with `OVERWRITE_SOURCE_FILE=true`.
- In-place mode without a backup is allowed but logs a warning at startup and per
  file.
- Existing target files are skipped when `OVERWRITE_EXISTING=false`.
- With `OVERWRITE_EXISTING=true`, the old output file is replaced only after the
  new file has been written successfully.
- Data is written to a temp file in the target directory and then atomically
  renamed.
- Errors on individual files do not stop the batch.
- Corrupt or unreadable files are logged as file errors.
- Without matching rules, the file is copied unchanged.
- No matching files: warning, exit code 0.
- Output directories are created as needed.

## 6. Logging and Exit Codes

Each file name is logged once; tag changes are shown as a table:

```text
  Tag         | Old Value | New Value
  ------------+-----------+----------
  series      | <leer>    | Old Album
  series-part | <leer>    | 3
  album       | Old Album | Old Title
```

Empty values use the current CLI marker `<leer>`. Times are also printed for
backup, copy, tag writing, target rename, and total.

| Code | Meaning |
| --- | --- |
| `0` | Success; in loop mode also normal shutdown via SIGINT/SIGTERM |
| `1` | At least one file could not be processed |
| `2` | Configuration error |

## 7. Linux Permissions

The fixer container runs as non-root with UID `1000`.

- `m4b_for_AudioBookShelf` and `m4b_backup` must be writable by UID 1000.
- If Docker creates the directories as `root`, the container cannot write to
  them. Create them and set permissions beforehand:

```bash
mkdir -p m4b_for_AudioBookShelf m4b_backup m4b_from_AudioBookConverter config
sudo chown -R 1000:1000 m4b_for_AudioBookShelf m4b_backup
```

- Same-directory and in-place modes require a writable `/data/in`. The default
  Compose setup deliberately mounts `/data/in` read-only; the mount must be
  changed for these modes.
- The ABS container runs as root unless a `user:` directive is set. If you run it
  with `user: "1000:1000"`, then `/config`, `/metadata`, and the library must also
  be writable by UID 1000.

## 8. ABS Stack

For the fixer and Audiobookshelf as one stack:

```text
examples/abs/
```

```bash
cd examples/abs
cp .env.example .env
# optional: cp override.env.example override.env
mkdir -p data/in data/out data/backup abs/config abs/metadata config
docker compose up -d --build
```

PowerShell:

```powershell
Set-Location examples/abs
Copy-Item .env.example .env
# optional: Copy-Item override.env.example override.env
New-Item -ItemType Directory -Force data/in, data/out, data/backup, abs/config, abs/metadata, config | Out-Null
docker compose up -d --build
```

The fixer writes to `data/out`; ABS mounts exactly that folder as `/audiobooks`.
The input folder `data/in` is not visible to ABS.

### ABS Scanning

ABS discovers new files through **periodic scans** or a manual scan. The ABS
documentation warns against running external tools with “Watch for file changes”
enabled on the same library. For this stack:

- Create the library at `/audiobooks`.
- Disable “Watch for file changes”.
- Enable periodic scans (for example every 15 minutes) or scan manually.

An API trigger after each fixer pass is **not** implemented. That would be a
separate feature and is not part of the file workflow.

### One Folder per Book

ABS expects a library structure with one folder per book. The example stack
therefore sets `REPLICATE_SOURCE_DIR_STRUCTURE=true`. If the input is already
organized one folder per book, that structure is mirrored under `data/out`.

### Do Not Write Directly into the ABS Library

`OVERWRITE_SOURCE_FILE=true` could modify the ABS library directly, but that is
not the default here:

- no idempotency marker other than the file itself
- in loop mode, every file would be rewritten on every pass
- ABS could scan while the file is being written
- source and library would not be separated

Separate-output mode with `OVERWRITE_EXISTING=false` is the safe default.

## 9. Troubleshooting

### ABS Still Shows Incorrect Tags

- Verify that the library points to `/audiobooks` (that is, `data/out`) and not to
  the input folder.
- Scan the library again.
- Check the file with ffprobe:
  ```bash
  ffprobe -v quiet -show_entries format_tags -of json -- "book.m4b"
  ```
- Expected: `show` and `episode_id` are set.
- For `.m4b`, `mvnm`/`mvin` are invisible without `-export_all`; that is normal.

### File Is Not Processed

- Check `FILENAME_FILTER` (default `*.m4b`).
- For subdirectories: set `RECURSIVE=true` or
  `REPLICATE_SOURCE_DIR_STRUCTURE=true`.
- If output already exists: set `OVERWRITE_EXISTING=true` or remove the target
  file.
- Files carrying `RENAME_SUFFIX` are intentionally skipped by `SKIP_SUFFIX=true`.

### Permission Denied

- Make the output and backup directories writable by UID 1000.
- Same-directory/in-place mode: `/data/in` must be writable; the default Compose
  setup is read-only.

### ABS Does Not Discover New Books

- Enable periodic scans or scan manually.
- Use the file watcher only if you accept the ABS warning about external tools.
- Verify that the file actually exists in `data/out`.

### Missing or Incorrect Series Sequence

- `series-part` must be an integer.
- When reading, `tvsh`/`tven` take precedence over `mvnm`/`mvin`.
- Use the default mapping only for AudioBookConverter sources.

### Docker Compose Error About `env_file`

`env_file.required` requires Compose ≥ 2.24. Older versions fail with a schema
error.

## 10. Security

- Do not commit `.env` or `override.env`.
- Backups contain complete audiobooks; protect access accordingly.
- Do not expose ABS directly to the internet; use a VPN or reverse proxy.
- The fixer does not require network access or an ABS API token.

## 11. GHCR

`.github/workflows/docker.yml` builds and pushes
`ghcr.io/yasuoiwakura/audiobook-tag-rewriter`:

- pushes to `main`, `dev`, `test`
- published releases
- manual `workflow_dispatch`

Tags: `latest` for `main`, branch names, commit SHA, branch SHA, and release tags.
Optionally, `vars.DOCKER_SHORT_NAME` enables a second GHCR image name.

## 12. Further Reading

- [`CONFIGURATION.md`](CONFIGURATION.md) – all options
- [`ARCHITECTURE.md`](ARCHITECTURE.md) – technical flow
- [`../examples/abs/README.md`](../examples/abs/README.md) – ABS stack
