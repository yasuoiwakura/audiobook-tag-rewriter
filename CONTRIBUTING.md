# Contributing

## 1. Requirements

- Python 3.12+
- Docker with Docker Compose ≥ 2.24 (for container tests only)
- Git

## 2. Development Environment

```bash
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

## 3. Tests and Linting

```bash
pytest
ruff check src tests
```

The tests create small synthetic MP4/M4B files with real mutagen MP4 tags. No real
audiobooks are required.

Before a pull request:

```bash
pytest
ruff check src tests
docker compose config
docker compose -f examples/abs/compose.yml config
```

## 4. Project Structure

```text
src/m4b_tag_fixer/
├── config.py       # environment/YAML/CLI, validation, default mapping
├── metadata.py     # MP4 atoms, mappings, rules
├── processor.py    # file discovery, backup, copy, atomic rename
└── main.py         # CLI, logging, loop, exit codes
```

- New configuration options must be added to `config.py`, YAML keys, the CLI,
  `.env.example`, `override.env.example`, `upstream.env`,
  `config.example.yml`, `doc/CONFIGURATION.md`, and `SPEC.md`.
- New metadata fields belong in `metadata.py` and in the tag table in
  `doc/CONFIGURATION.md`.
- Behavioral changes require tests in `tests/`.

## 5. Features and Documentation

Feature conventions are documented in
[`doc/FEATURES/README.md`](doc/FEATURES/README.md):

- branch: `matt-nnnn`
- file: `feat-nnnn-kebab-case-title.md`
- status: `planned`, `in progress`, `implemented`, `discarded`
- each feature documents goal, configuration, behavior, acceptance criteria,
  tests, and documentation

Documentation structure:

| File | Content |
| --- | --- |
| `README.md` | Overview, problem, quick start, stack |
| `doc/PROBLEM.md` | Problem, root cause, decision, alternatives |
| `doc/ARCHITECTURE.md` | Components, flow, idempotency |
| `doc/CONFIGURATION.md` | All options |
| `doc/OPERATIONS.md` | Docker, backup, troubleshooting |
| `SPEC.md` | Implementation status and acceptance criteria |
| `doc/FEATURES/` | Feature inventory |
| `doc/archive/README.de.md` | Frozen German README snapshot |

## 6. Pull-Request Checklist

- [ ] `pytest` passes
- [ ] `ruff check src tests` passes
- [ ] Compose files validate
- [ ] New/changed options are documented in all configuration paths
- [ ] `README.md` and relevant `doc/` files are updated
- [ ] `SPEC.md` is updated for behavioral changes
- [ ] No `.env`, backups, audiobooks, or credentials are committed

## 7. Security

- Do not commit secrets, tokens, or credentials.
- Keep `.env` and `override.env` local.
- Backups contain complete audiobooks and do not belong in the repository.
- The fixer does not require network access.
