# Konfiguration

## 1. Präzedenz

Es gibt vier Ebenen. Später genannte Quellen überschreiben frühere:

1. eingebaute Defaults
2. YAML-Datei (`CONFIG_FILE` oder `--config`)
3. `.env` / Prozess-Umgebungsvariablen
4. Kommandozeilenargumente

Beim direkten Python-Aufruf wird `.env` im aktuellen Arbeitsverzeichnis geladen.
Vorhandene Prozessvariablen haben Vorrang. Alternativ: `--env-file` oder
`ENV_FILE`.

## 2. Umgebungsvariablen

| Variable | Default | Bedeutung |
| --- | --- | --- |
| `INPUT_DIR` | `/in` | Eingabeverzeichnis (nicht nötig bei Einzeldatei) |
| `OUTPUT_DIR` | `/out` | Ausgabeverzeichnis |
| `FILENAME_FILTER` | `*.m4b` | Glob-Muster für Dateinamen |
| `TAG_MAP` | – | JSON-Liste von Tag-Mappings |
| `TAG_RULES` | – | JSON-Liste von Wert-Ersetzungen |
| `RECURSIVE` | `false` | Unterverzeichnisse einbeziehen und Struktur spiegeln |
| `REPLICATE_SOURCE_DIR_STRUCTURE` | `false` | Rekursiv suchen und Quellstruktur unter `OUTPUT_DIR` nachbilden |
| `OUTPUT_SUFFIX` | `false` | `RENAME_SUFFIX` immer an Ausgabedateien anhängen |
| `OVERWRITE_EXISTING` | `false` | Vorhandene Ausgabedateien überschreiben |
| `OVERWRITE_SOURCE_FILE` | `false` | Quelle in-place überschreiben; Backup dringend empfohlen |
| `OUTPUT_SAME_DIR` | `false` | Kopie im Quellordner ablegen statt in `OUTPUT_DIR` |
| `RENAME_SUFFIX` | `[TAGS_REMAPPED]` | Suffix-Text für Ausgabedateien |
| `SKIP_SUFFIX` | `true` | Dateien mit diesem Suffix nicht erneut verarbeiten |
| `BACKUP` | `false` | Eingabedatei vor der Verarbeitung sichern |
| `BACKUP_DIR` | – | Zielverzeichnis für Backups; bei `BACKUP=true` erforderlich |
| `BACKUP_RETENTION_DAYS` | `30` | Backups älter als N Tage löschen; `0` deaktiviert |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, ... |
| `LOOP` | `false` | Dauerbetrieb (Compose: `true`) |
| `LOOP_INTERVAL` | `60` | Sekunden zwischen Loop-Durchläufen; muss > 0 sein |
| `SINGLE_FILE` | – | Genau diese `.m4b`-Datei verarbeiten |
| `CONFIG_FILE` | – | Pfad zur optionalen YAML-Konfiguration |
| `ENV_FILE` | `.env` | Pfad zur `.env`-Datei |

Boolesche Werte: `true/false`, `1/0`, `yes/no`, `on/off`, `ja/nein`.

### Env-Dateien für Compose

Im Root-`compose.yml` werden drei Dateien in dieser Reihenfolge geladen:

1. `upstream.env` (committed Defaults)
2. `override.env` (optional, ignored)
3. `.env` (optional, ignored)

Spätere Dateien überschreiben frühere Werte. Compose-Interpolation mit `${VAR}`
liest nur `.env`; die App-Konfiguration wird über `env_file` durchgereicht.

```bash
cp override.env.example override.env   # optional
cp .env.example .env                   # optional
```

Host-Pfade der Mounts sind Compose-Interpolationsvariablen und gehören in `.env`:

```dotenv
HOST_INPUT_DIR=./m4b_from_AudioBookConverter
HOST_OUTPUT_DIR=./m4b_for_AudioBookShelf
HOST_BACKUP_DIR=./m4b_backup
HOST_CONFIG_DIR=./config
```

## 3. Dateinamenfilter

- Der Filter gilt nur für den Dateinamen, nicht für Unterverzeichnisse.
- Der Vergleich ist case-insensitiv; zusätzlich muss die Endung `.m4b` sein.
- Standardmäßig werden nur Dateien direkt in `INPUT_DIR` verarbeitet.
- `RECURSIVE=true` bezieht Unterverzeichnisse ein und spiegelt die Struktur unter
  `OUTPUT_DIR`.
- `REPLICATE_SOURCE_DIR_STRUCTURE=true` durchsucht `INPUT_DIR` rekursiv und bildet
  die Unterverzeichnisse unter `OUTPUT_DIR` nach; Dateinamen bleiben unverändert.
  `RECURSIVE` muss dafür nicht zusätzlich gesetzt werden.
- Dateien, deren Basisname bereits mit `RENAME_SUFFIX` endet, werden bei
  `SKIP_SUFFIX=true` nicht erneut verarbeitet.

Beispiel:

```text
INPUT_DIR/German/book.m4b -> OUTPUT_DIR/German/book.m4b
```

## 4. Suffix und Überschreiben

> **Warnung:** `OVERWRITE_SOURCE_FILE=true` überschreibt die Quelldatei
> unwiderruflich. `BACKUP=true` wird dringend empfohlen. Ohne Backup läuft die
> Verarbeitung trotzdem, protokolliert aber pro Datei eine Warnung.

- `OUTPUT_SUFFIX=false` (Default): Der Suffix wird nur als Sicherheitsnetz
  angehängt, wenn der Zielpfad sonst identisch mit der Quelle wäre und
  `OVERWRITE_SOURCE_FILE=false` ist.
- `OUTPUT_SUFFIX=true`: Der Suffix wird immer angehängt (nicht doppelt, falls er
  bereits im Namen steht).
- `OUTPUT_SAME_DIR=true`: Der Zielpfad ist die Quelle selbst. Ohne
  `OVERWRITE_SOURCE_FILE=true` wird deshalb automatisch der Suffix angehängt.
- `OVERWRITE_SOURCE_FILE=true`: Die Quelle wird in-place überschrieben.
  `BACKUP=true` ist dringend empfohlen. `OUTPUT_SUFFIX=true` hat Vorrang und
  erzeugt stattdessen eine Kopie mit Suffix; die Quelle bleibt dann unverändert.
- Ein leerer `RENAME_SUFFIX` ist im Same-Dir-Modus nur mit
  `OVERWRITE_SOURCE_FILE=true` erlaubt.
- `OUTPUT_DIR` und `INPUT_DIR` dürfen nicht identisch sein.

| Zielmodus | `OUTPUT_SUFFIX` | `OVERWRITE_SOURCE_FILE` | Ergebnis |
| --- | --- | --- | --- |
| Replicate/Recursive | `false` | egal | `out/German/book.m4b` |
| Replicate/Recursive | `true` | egal | `out/German/book [TAGS_REMAPPED].m4b` |
| Same-Dir | `false` | `false` | `book [TAGS_REMAPPED].m4b` (Schutz) |
| Same-Dir | `false` | `true` | Quelle wird in-place überschrieben |
| Same-Dir | `true` | egal | `book [TAGS_REMAPPED].m4b` (explizit) |
| Flach | `false` | egal | `out/book.m4b` |
| Flach | `true` | egal | `out/book [TAGS_REMAPPED].m4b` |

Im Loop-Modus wird eine in-place verarbeitete Datei bei jedem Durchlauf erneut
verarbeitet. Für einen dauerhaften Eingang ist der Separate-Output-Modus daher
die bessere Wahl.

## 5. TAG_MAP (Tag-zu-Tag-Mapping)

`TAG_MAP` ist eine JSON-Liste. Jeder Eintrag benötigt `from` und `to`
(alternativ `source` und `target`).

```json
[
  {"from": "album", "to": "series"},
  {"from": "track", "to": "series-part"},
  {"from": "title", "to": "album"}
]
```

- Wird ein Mapping angegeben, ersetzt es das Default-Mapping vollständig.
- `TAG_MAP=[]` deaktiviert das Default-Mapping.
- Mappings werden in Reihenfolge ausgeführt; jede Regel liest den aktuellen
  Zwischenstand. Dadurch sind auch Ketten möglich.
- Fehlt die Quelle, wird der Eintrag protokolliert und übersprungen.
- Das Ziel wird bei Erfolg überschrieben; der vorherige Zielwert wird geloggt.
- `series-part`/`mvin` erwartet eine Ganzzahl.
- Unbekannte Tags, fehlende Pflichtfelder und ungültiges JSON führen zu
  Exit-Code 2.

### Default-Mapping

Ohne `TAG_MAP` und ohne `TAG_RULES`:

| Quelle | Ziel | MP4-Atome |
| --- | --- | --- |
| `album` | `series` | `tvsh` + `mvnm` |
| `track` | `series-part` | `tven` + `mvin` (Integer) |
| `title` | `album` | `©alb` |

Mappings **kopieren** Werte; die Quelle bleibt erhalten. `title -> album`
überschreibt also bewusst das bisherige Album, nachdem es zuvor nach `series`
kopiert wurde.

Nur `TAG_RULES` gesetzt? Dann gilt **kein** Default-Mapping, weil eine explizite
Änderungsangabe vorhanden ist. Mappings laufen immer vor den Wert-Ersetzungen.

## 6. TAG_RULES (Wert-Ersetzungen)

`TAG_RULES` ersetzt vorhandene Werte exakt. Es gibt keine Teilstring-Ersetzung.

```json
[
  {"tag": "album", "old": "Old Album", "new": "New Album"},
  {"tag": "artist", "old": "Old Author", "new": "New Author"},
  {"tag": "track", "old": "3", "new": "7"}
]
```

- Regeln laufen nach allen Mappings, in der angegebenen Reihenfolge.
- Nur exakt passende Werte werden ersetzt (Groß-/Kleinschreibung inklusive).
- Mehrwertige Felder: nur exakt passende Werte werden ersetzt, andere bleiben.
- Fehlende Tags und nicht passende Werte sind kein Fehler, werden aber geloggt.
- `track` wird ohne führende Nullen gelesen/verglichen; die Gesamttrackzahl bleibt.
- Ungültiges JSON, fehlende Pflichtfelder, unbekannte Tags, identische `old`/`new`
  und nicht-numerische Track-Werte führen zu Exit-Code 2.
- `TAG_RULES=[]` erlaubt einen Lauf ohne Wert-Ersetzungen (und deaktiviert zusammen
  mit fehlendem `TAG_MAP` das Default-Mapping).

## 7. Unterstützte Tags

| Regelname | MP4-Atom | Hinweis |
| --- | --- | --- |
| `album` | `©alb` | Album |
| `artist` | `©ART` | Interpret / Autor |
| `title` | `©nam` | Titel |
| `albumartist` | `aART` | Albuminterpret |
| `track` | `trkn` | Tracknummer; Gesamtzahl bleibt erhalten |
| `year` | `©day` | Jahr / Datum |
| `genre` | `©gen` | Genre |
| `composer` | `©wrt` | Komponist / bei Hörbüchern oft Sprecher |
| `comment` | `©cmt` | Kommentar |
| `grouping` | `©grp` | Gruppierung |
| `description` | `desc` | Beschreibung |
| `subtitle` | `©st3` | Untertitel |
| `publisher` | `©pub` | Verlag |
| `series` | `tvsh` + `mvnm` | Serie; `tvsh` = ABS/ffprobe `show` |
| `series-part` | `tven` + `mvin` | Seriennummer; `tven` = `episode_id`, `mvin` = Integer |
| `language` | `lang` | Sprache |
| `isbn` | `----:com.apple.iTunes:ISBN` | Freeform |
| `asin` | `----:com.apple.iTunes:ASIN` | Freeform |

Aliase:

- `album-artist`, `album_artist` → `albumartist`
- `author` → `artist`
- `narrator` → `composer`
- `mvnm`/`show` → `series`
- `mvin`/`episode_id`/`series_part` → `series-part`
- `lang` → `language`
- `audible_asin`, `audible-asin` → `asin`

`mvin` wird als echtes MP4-Integer-Atom geschrieben, `tven` als Text. Beim Lesen
haben `tvsh`/`tven` Vorrang vor `mvnm`/`mvin`. Cover (`covr`), Kapitel (`chpl`)
und andere vorhandene Atome bleiben beim Speichern erhalten.

## 8. YAML-Konfiguration

Aktivieren mit `--config` oder `CONFIG_FILE`.

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

# optional, zusätzlich zum Mapping:
# tag_rules:
#   - tag: album
#     old: Old Album
#     new: New Album
```

Eine vollständige Vorlage liegt als `config.example.yml` bei. Für Docker:

```bash
mkdir -p config
cp config.example.yml config/config.yml
```

und in `.env`:

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

`PYTHONPATH=src` ist nötig, wenn das Paket nicht installiert wurde. `run.bat`
setzt dies automatisch.

## 10. Validierung

Exit-Code `2` bei Konfigurationsfehlern, unter anderem:

- `INPUT_DIR` existiert nicht oder ist kein Verzeichnis.
- `INPUT_DIR == OUTPUT_DIR`.
- `OUTPUT_DIR` liegt bei rekursiver Verarbeitung innerhalb von `INPUT_DIR`.
- `BACKUP=true` ohne `BACKUP_DIR`.
- `BACKUP_DIR` ist identisch mit `INPUT_DIR` oder `OUTPUT_DIR`.
- `BACKUP_DIR` liegt bei rekursiver Verarbeitung innerhalb von `INPUT_DIR`.
- Ungültige boolesche, numerische oder JSON-Werte.
- Unbekannte YAML-Schlüssel oder Tags.
- `RENAME_SUFFIX` enthält ungültige Dateinamenzeichen.
- Same-Dir mit leerem Suffix ohne `OVERWRITE_SOURCE_FILE=true`.

## 11. Weiterführend

- [`OPERATIONS.md`](OPERATIONS.md) – Docker, Backup und Troubleshooting
- [`ARCHITECTURE.md`](ARCHITECTURE.md) – technischer Ablauf
- [`PROBLEM.md`](PROBLEM.md) – warum das Mapping nötig ist
