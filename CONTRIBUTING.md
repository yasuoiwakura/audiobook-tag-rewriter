# Beitragen

## 1. Voraussetzungen

- Python 3.12+
- Docker mit Docker Compose ≥ 2.24 (nur für Container-Tests)
- Git

## 2. Entwicklungsumgebung

```bash
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

## 3. Tests und Linting

```bash
pytest
ruff check src tests
```

Die Tests erzeugen kleine synthetische MP4/M4B-Dateien mit echten
mutagen-MP4-Tags. Es werden keine realen Hörbücher benötigt.

Vor einem Pull Request:

```bash
pytest
ruff check src tests
docker compose config
docker compose -f examples/abs/compose.yml config
```

## 4. Projektstruktur

```text
src/m4b_tag_fixer/
├── config.py       # Env/YAML/CLI, Validierung, Default-Mapping
├── metadata.py     # MP4-Atome, Mapping, Regeln
├── processor.py    # Dateisuche, Backup, Kopie, atomarer Rename
└── main.py         # CLI, Logging, Loop, Exit-Codes
```

- Neue Konfigurationsoptionen müssen in `config.py`, YAML-Keys, CLI,
  `.env.example`, `override.env.example`, `upstream.env`,
  `config.example.yml`, `doc/CONFIGURATION.md` und `SPEC.md` ergänzt werden.
- Neue Metadatenfelder gehören in `metadata.py` und die Tag-Tabelle in
  `doc/CONFIGURATION.md`.
- Verhaltensänderungen brauchen Tests in `tests/`.

## 5. Features und Dokumentation

Die Feature-Konventionen stehen in [`doc/FEATURES/README.md`](doc/FEATURES/README.md):

- Branch: `matt-nnnn`
- Datei: `feat-nnnn-kebab-case-titel.md`
- Status: `geplant`, `in Umsetzung`, `umgesetzt`, `verworfen`
- Jedes Feature dokumentiert Ziel, Konfiguration, Verhalten,
  Akzeptanzkriterien, Tests und Doku.

Dokumentationsstruktur:

| Datei | Inhalt |
| --- | --- |
| `README.md` | Einstieg, Problem, Quick Start, Stack |
| `doc/PROBLEM.md` | Problem, Ursache, Entscheidung, Alternativen |
| `doc/ARCHITECTURE.md` | Komponenten, Ablauf, Idempotenz |
| `doc/CONFIGURATION.md` | alle Optionen |
| `doc/OPERATIONS.md` | Docker, Backup, Troubleshooting |
| `SPEC.md` | Implementierungsstand und Abnahmekriterien |
| `doc/FEATURES/` | Feature-Inventar |

## 6. Pull-Request-Checkliste

- [ ] `pytest` erfolgreich
- [ ] `ruff check src tests` erfolgreich
- [ ] Compose-Dateien validieren
- [ ] Neue/geänderte Optionen in allen Konfigurationswegen dokumentiert
- [ ] `README.md` und relevante `doc/`-Dateien aktualisiert
- [ ] `SPEC.md` bei Verhaltensänderungen aktualisiert
- [ ] Keine `.env`, Backups, Hörbücher oder Zugangsdaten committet

## 7. Sicherheit

- Keine Secrets, Tokens oder Zugangsdaten committen.
- `.env` und `override.env` bleiben lokal.
- Backups enthalten vollständige Hörbücher und gehören nicht ins Repository.
- Der Fixer benötigt keinen Netzwerkzugriff.
