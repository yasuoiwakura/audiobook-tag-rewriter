# SPEC – m4b-tag-fixer

Stand: 2026-10-21  
Version: 0.1.0  
Status: lauffähiges MVP; ABS-Series-Mapping, Copy-Suffix-Modus, Input-Backup,
Struktur-Spiegelung und In-Place-Overwrite umgesetzt

## 1. Zweck

`m4b-tag-fixer` liest und schreibt MP4-Metadaten in `.m4b`-Hörbuchdateien. Ziel ist
es, die von AudioBookConverter erzeugten Tags so aufzubereiten, dass
Audiobookshelf (ABS) Titel, Autor, Sprecher, Serie und Seriennummer korrekt
importiert.

Problem, Ursachenkette und verworfene Alternativen sind in
[`doc/PROBLEM.md`](doc/PROBLEM.md) dokumentiert.

Im Standardmodus werden die Quelldateien nicht verändert; es wird eine Kopie
bearbeitet. Mit `OVERWRITE_SOURCE_FILE=true` kann die Quelle explizit in-place
überschrieben werden; ein Backup wird dringend empfohlen.

## 2. Aktueller Implementierungsstand

### 2.1 Verarbeitung

- Standard-Eingabe: `/in`
- Standard-Ausgabe: `/out`
- Docker: `/data/in` (AudioBookConverter) → `/data/out` (AudioBookShelf)
- Docker-Backup: `/data/backup`
- Alternative: Kopie im Quellordner mit Suffix (`OUTPUT_SAME_DIR=true`)
- Dateisuche: nur `.m4b`, optional rekursiv
- Optional rekursive Suche mit Spiegelung der Quellstruktur
  (`REPLICATE_SOURCE_DIR_STRUCTURE=true`); Dateinamen bleiben unverändert
- Optional `OUTPUT_SUFFIX=true`, um `RENAME_SUFFIX` immer anzuhängen
- Optional In-Place-Überschreiben der Quelle (`OVERWRITE_SOURCE_FILE=true`);
  `BACKUP=true` dringend empfohlen
- Dateinamenfilter: Glob, case-insensitiv, standardmäßig `*.m4b`
- Kein Re-Encoding der Audiodaten
- Optionales Backup der Eingabedatei vor der Verarbeitung (`BACKUP=true`)

Ablauf pro Datei:

1. Tags der Quelle lesen
2. Mappings und Wert-Ersetzungen im Speicher berechnen
3. Optional die Quelle nach `BACKUP_DIR` sichern
4. Quelle per `shutil.copy2` in eine Temp-Datei im Zielverzeichnis kopieren
5. Tags in der Temp-Datei mit Mutagen ändern
6. Temp-Datei atomar auf den Zielnamen verschieben
7. Beim Durchlauf alte Backups gemäß `BACKUP_RETENTION_DAYS` bereinigen
   (im Loop höchstens stündlich)

Same-Dir-Modus:

- Zielname: `<basename> <suffix>.m4b`
- Beispiel: `Buch [TAGS_REMAPPED].m4b`
- Quelle bleibt unverändert, solange `OVERWRITE_SOURCE_FILE=false` ist.
- Mit `OVERWRITE_SOURCE_FILE=true` wird die Quelle in-place überschrieben;
  `BACKUP=true` ist dringend empfohlen, aber nicht Pflicht.
- `OUTPUT_SUFFIX=true` hat Vorrang und erzeugt auch bei erlaubtem
  Source-Overwrite eine Kopie mit Suffix.
- Bereits suffixed Dateien werden bei `SKIP_SUFFIX=true` übersprungen.
- Vorhandene Zieldateien werden bei `OVERWRITE_EXISTING=false` übersprungen.

Suffix-Regel:

- `OUTPUT_SUFFIX=true`: Suffix wird immer angehängt (idempotent).
- `OUTPUT_SUFFIX=false`: Suffix nur, wenn der Zielpfad sonst identisch mit der
  Quelle wäre und `OVERWRITE_SOURCE_FILE=false` ist.
- Replicate/Recursive hängen ohne `OUTPUT_SUFFIX` keinen Suffix an.
- Ein leerer `RENAME_SUFFIX` ist im Same-Dir-Modus nur mit
  `OVERWRITE_SOURCE_FILE=true` zulässig.

### 2.2 Konfiguration

Unterstützt werden:

- Environment Variables
- `.env` (auch beim direkten Python-Aufruf)
- YAML (`CONFIG_FILE` / `--config`)
- CLI-Argumente
- Einzeldatei als positionsloses Argument

Präzedenz: Defaults < YAML < `.env`/Env < CLI.

Wichtige Variablen:

| Variable | Default | Bedeutung |
| --- | --- | --- |
| `INPUT_DIR` | `/in` | Eingabeverzeichnis |
| `OUTPUT_DIR` | `/out` | Ausgabeverzeichnis |
| `FILENAME_FILTER` | `*.m4b` | Dateinamenfilter |
| `TAG_MAP` | – | JSON-Liste von Tag-zu-Tag-Mappings |
| `TAG_RULES` | – | JSON-Liste von Wert-Ersetzungen |
| `RECURSIVE` | `false` | Unterverzeichnisse einbeziehen |
| `REPLICATE_SOURCE_DIR_STRUCTURE` | `false` | Rekursiv suchen und Quellstruktur unter `OUTPUT_DIR` nachbilden |
| `OUTPUT_SUFFIX` | `false` | `RENAME_SUFFIX` immer an Ausgabedateien anhängen |
| `OVERWRITE_EXISTING` | `false` | Vorhandene Ausgabe überschreiben |
| `OVERWRITE_SOURCE_FILE` | `false` | Quelle in-place überschreiben; `BACKUP=true` dringend empfohlen |
| `OUTPUT_SAME_DIR` | `false` | Kopie im Quellordner ablegen |
| `RENAME_SUFFIX` | `[TAGS_REMAPPED]` | Suffix-Text für Ausgabedateien |
| `SKIP_SUFFIX` | `true` | Bereits suffixed Dateien überspringen |
| `BACKUP` | `false` | Eingabedatei vor der Verarbeitung sichern |
| `BACKUP_DIR` | – | Zielverzeichnis für Backups; bei `BACKUP=true` erforderlich |
| `BACKUP_RETENTION_DAYS` | `30` | Backups älter als N Tage löschen; `0` deaktiviert |
| `LOG_LEVEL` | `INFO` | Log-Level |
| `LOOP` | `false` | Dauerbetrieb (Compose: `true`) |
| `LOOP_INTERVAL` | `60` | Sekunden zwischen Loop-Läufen |
| `SINGLE_FILE` | – | Genau eine Datei verarbeiten |
| `CONFIG_FILE` | – | Pfad zur YAML-Konfiguration |
| `ENV_FILE` | `.env` | Pfad zur `.env` |

### 2.3 Default-Mapping

Ohne `TAG_MAP` und ohne `TAG_RULES`:

| Quelle | Ziel | Geschriebene MP4-Atome |
| --- | --- | --- |
| `album` | `series` | `tvsh` + `mvnm` |
| `track` | `series-part` | `tven` + `mvin` (Integer) |
| `title` | `album` | `©alb` |

Mappings werden vor Wert-Ersetzungen ausgeführt. Explizite `TAG_MAP`-Einträge
ersetzen das Default-Mapping vollständig.

### 2.4 Unterstützte logische Tags

`album`, `artist`, `title`, `albumartist`, `track`, `year`, `genre`, `composer`,
`comment`, `grouping`, `description`, `subtitle`, `publisher`, `series`,
`series-part`, `language`, `isbn`, `asin`.

Aliase: `album-artist`/`album_artist`, `author`, `narrator`, `mvnm`/`show`,
`mvin`/`episode_id`, `series_part`, `lang`, `audible_asin`/`audible-asin`.

### 2.5 Docker

`compose.yml` (nicht `docker-compose.yml`):

- Eine Datei mit `build: .` und
  `image: ghcr.io/yasuoiwakura/audiobook-tag-rewriter:${IMAGE_TAG:-latest}`
- `docker compose up --build` baut lokal
- `docker compose pull && docker compose up --no-build` nutzt das GHCR-Image
- Compose-Service mit Loop (`LOOP=true`, `LOOP_INTERVAL=60`)
- `restart: on-failure`
- `HOST_INPUT_DIR` (Default `./m4b_from_AudioBookConverter`) → `/data/in`
  (read-only, Eingang)
- `HOST_OUTPUT_DIR` (Default `./m4b_for_AudioBookShelf`) → `/data/out`
  (read-write, Ausgang)
- `HOST_BACKUP_DIR` (Default `./m4b_backup`) → `/data/backup` (read-write, Backup)
- `HOST_CONFIG_DIR` (Default `./config`) → `/config` (read-only, optionale YAML)
- Container läuft als non-root (UID 1000)

Env-Reihenfolge über `env_file`:

1. `upstream.env` (committed Defaults)
2. `override.env` (optional, ignored)
3. `.env` (optional, ignored)

Spätere Dateien überschreiben frühere Werte. `upstream.env` setzt `BACKUP=true`.
`BACKUP=false` in `override.env` oder `.env` schaltet das Backup ab.

`HOST_*`, `IMAGE_TAG` und andere Compose-Interpolationsvariablen werden nicht aus
`env_file` gelesen. Sie kommen aus der Shell oder aus `.env`; ohne `.env` gelten
die Defaults aus `compose.yml`. `.env` bleibt optional.

Zusätzlich gibt es einen eigenständigen Beispiel-Stack unter
[`examples/abs/`](examples/abs/README.md). Er startet Fixer und Audiobookshelf
gemeinsam; der Fixer schreibt nach `data/out`, das ABS als `/audiobooks` mountet.
Der Beispiel-Stack nutzt eigene `upstream.env`/`override.env`-Dateien und setzt
`REPLICATE_SOURCE_DIR_STRUCTURE=true`, damit die ABS-Struktur mit einem Ordner pro
Buch erhalten bleibt.

`OUTPUT_SAME_DIR=true` benötigt ein beschreibbares Quellverzeichnis. Das
Standard-Compose mountet `/data/in` read-only; für Same-Dir müsste der Mount
entsprechend angepasst werden.

Logging:

- Pro Datei wird der Name einmal geloggt.
- Tag-Änderungen erscheinen als Tabelle `Tag | Old Value | New Value`; leere
  Werte als `<leer>`.
- Zeiten werden für Backup, Kopieren, Tags, Ziel-Rename und Gesamt ausgegeben.
- Leere oder reine Skip-Loop-Runden werden nur auf `DEBUG` geloggt.
- `LOG_LEVEL=INFO` ist im Leerlauf still; `WARNING`/`ERROR` reduzieren weiter.

### 2.6 Verifikation

- `pytest`: 128 Tests erfolgreich
- `ruff check src tests`: erfolgreich
- `docker compose config`: erfolgreich validiert
- `docker compose -f examples/abs/compose.yml config`: erfolgreich validiert
- Docker-Build/Container-Start: **nicht verifiziert**, weil der Docker-Daemon in
  der Entwicklungsumgebung nicht lief

## 3. Series-Mapping

### 3.1 Geschriebene Atome

| Logisch | MP4-Atome | ffprobe-Key ohne `-export_all` | ABS-Mapping |
| --- | --- | --- | --- |
| `series` | `tvsh`, `mvnm` | `show` | Series |
| `series-part` | `tven`, `mvin` | `episode_id` | Series Sequence |

`tven` wird als Text geschrieben, `mvin` als echtes MP4-Integer-Atom.

Beim Lesen haben `tvsh`/`tven` Vorrang. Falls sie fehlen, werden `mvnm`/`mvin`
gelesen. Damit bleiben ältere Ausgabedateien kompatibel.

### 3.2 Warum zusätzlich tvsh/tven?

- ABS ruft ffprobe ohne `-export_all` auf.
- `mvnm`/`mvin` sind bei MP4/M4B für ffprobe unbekannte Atome und erscheinen erst
  mit `-export_all`.
- `tvsh`/`tven` werden von ffprobe als `show`/`episode_id` ausgegeben und von ABS
  bereits auf Series/Series Sequence gemappt.
- `mvnm`/`mvin` bleiben zusätzlich erhalten, damit andere Player sie finden.

### 3.3 Verifikation

Synthetische M4B-Datei nach dem Mapping:

```text
ohne -export_all:  show = Old Album, episode_id = 3
mit -export_all:   zusätzlich mvnm = Old Album, mvin = 3
```

Damit ist der von ABS erwartete ffprobe-Pfad über `show`/`episode_id` vorhanden; ein tatsächlicher ABS-Scan wurde in dieser Umgebung nicht ausgeführt.

## 4. Bekannte Einschränkungen

1. **Immer vollständige Kopie:** Auch unveränderte Dateien werden kopiert. Bei
   einer 834-MB-Datei wurden ca. 73 Sekunden gemessen (Kopie plus
   `mdat`-Verschiebung durch Mutagen).
2. **MP4-Layout:** Bei `moov` vor `mdat` verschiebt jede Tag-Vergrößerung den
   `mdat`-Block. Das ist kein Kopierproblem, sondern eine Eigenschaft des
   MP4-Layouts und von Mutagen.
3. **Kein Move-Modus:** Quelldateien werden weder verschoben noch gelöscht. Ein
   In-Place-Overwrite ist über `OVERWRITE_SOURCE_FILE=true` möglich, aber im Loop
   nicht idempotent.
4. **Backup kostet Speicher/Zeit:** `BACKUP=true` kopiert die Eingabedatei
   vollständig nach `BACKUP_DIR`. Alte Backups werden nach
   `BACKUP_RETENTION_DAYS` bereinigt.
5. **Docker-Build/Container-Start** wurden in dieser Umgebung nicht ausgeführt;
   `docker compose config` wird validiert.
6. **Same-Dir im Container** benötigt einen beschreibbaren `/data/in`-Mount.

## 5. Optionale nächste Schritte

Nicht implementiert, nur vorgemerkt:

- `MODE=move`: In-Place-Bearbeitung plus nativer Rename, Fallback Copy+Delete
- Reflink/CoW-Kopie, wenn das Dateisystem es unterstützt
- Layout-Analyse/Warnung vor großem `mdat`-Shift
- zusätzliche Metadatenfelder oder freiform-basierte Serien-Tags

## 6. Abnahmekriterien

Erfüllt:

1. `series` wird als `tvsh` und `mvnm` geschrieben.
2. `series-part` wird als `tven` und `mvin` geschrieben.
3. ffprobe ohne `-export_all` zeigt `show` und `episode_id`.
4. Same-Dir-Modus erzeugt `<basename> [TAGS_REMAPPED].m4b`.
5. Quell-Hash bleibt vor/nach der Verarbeitung identisch.
6. Tests und Ruff laufen erfolgreich.
7. README, `.env.example`, `upstream.env`, `override.env.example` und
   `config.example.yml` sind aktualisiert.
8. `compose.yml` nutzt mehrere Env-Dateien und die drei Daten-Mounts.
9. Der GHCR-Workflow baut und pusht das Image.
10. `compose.yml` unterstützt lokalen Build und Prebuilt-Image ohne zusätzliche
    Compose-Datei.
11. Die Dokumentation ist in `README.md`, `doc/PROBLEM.md`,
    `doc/ARCHITECTURE.md`, `doc/CONFIGURATION.md`, `doc/OPERATIONS.md` und
    `CONTRIBUTING.md` strukturiert und gegenseitig verlinkt.
12. `examples/abs/` bietet einen validen Compose-Stack mit Fixer und
    Audiobookshelf; `data/out` ist die ABS-Library und `data/in` bleibt
    read-only.

## 7. Referenzen

- AudioBookConverter Issue #759: Metadaten-Mapping für Audiobookshelf
  <https://github.com/yermak/AudioBookConverter/issues/759>
- Audiobookshelf Issue #5669: separates Mapping für M4B
  <https://github.com/advplyr/audiobookshelf/issues/5669>
- Audiobookshelf Issue #2471: movementname/movement vs. mvnm/mvin
  <https://github.com/advplyr/audiobookshelf/issues/2471>
- Audiobookshelf-Dokumentation „Book Library Structure“
  <https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/>
- ABS-Quellen:
  - `server/libs/nodeFfprobe/index.js`
  - `server/utils/prober.js`
  - `server/scanner/AudioFileScanner.js`
- Issue-Entwurf für das ABS-Repository: [`ABS-issue-readtags.md`](ABS-issue-readtags.md)
  (englisch)
- Projektproblem und Entscheidung: [`doc/PROBLEM.md`](doc/PROBLEM.md)
- Technischer Ablauf: [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md)
- Alle Optionen: [`doc/CONFIGURATION.md`](doc/CONFIGURATION.md)
- Betrieb und Troubleshooting: [`doc/OPERATIONS.md`](doc/OPERATIONS.md)
- Fixer + ABS als Stack: [`examples/abs/`](examples/abs/README.md)
