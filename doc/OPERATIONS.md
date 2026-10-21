# Betrieb

## 1. Voraussetzungen

- Docker mit Docker Compose **≥ 2.24** (wegen `env_file.required`)
- Optional für lokale Entwicklung: Python 3.12+ und `pip`
- Für den ABS-Stack: Audiobookshelf-Image `ghcr.io/advplyr/audiobookshelf`

## 2. Root-Compose: nur der Fixer

```bash
mkdir -p m4b_from_AudioBookConverter m4b_for_AudioBookShelf m4b_backup config
docker compose up --build
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force m4b_from_AudioBookConverter, m4b_for_AudioBookShelf, m4b_backup, config | Out-Null
docker compose up --build
```

Das Root-`compose.yml` startet den Fixer im Loop-Modus. Der Eingang ist
read-only, der Ausgang und das Backup sind read-write.

| Host (Default / Env) | Container | Zugriff | Bedeutung |
| --- | --- | --- | --- |
| `./m4b_from_AudioBookConverter` / `HOST_INPUT_DIR` | `/data/in` | read-only | Eingang |
| `./m4b_for_AudioBookShelf` / `HOST_OUTPUT_DIR` | `/data/out` | read-write | Ausgang / ABS-Library |
| `./m4b_backup` / `HOST_BACKUP_DIR` | `/data/backup` | read-write | Backup |
| `./config` / `HOST_CONFIG_DIR` | `/config` | read-only | optionale YAML |

Relative Host-Pfade beziehen sich auf das Verzeichnis der Compose-Datei.

### Prebuilt-Image statt lokaler Build

```bash
docker compose pull
docker compose up --no-build
```

`compose.yml` enthält bewusst `build: .` und `image:`. `--build` baut lokal,
`pull` verwendet das veröffentlichte GHCR-Image. `IMAGE_TAG` ist standardmäßig
`latest`.

### Einmal-Lauf statt Loop

```bash
LOOP=false docker compose up --build
```

PowerShell:

```powershell
$env:LOOP='false'; docker compose up --build
```

Nur ein Durchlauf mit Exit-Code für Skripte:

```bash
docker compose run --rm -e LOOP=false m4b-tag-fixer
```

## 3. Loop-Modus

- `LOOP=true`: Der Prozess bleibt aktiv und scannt alle `LOOP_INTERVAL` Sekunden.
- Leere Runden und reine Skip-Runden werden nur auf `DEBUG` geloggt.
- `INFO` zeigt nach dem Start nur echte Verarbeitung.
- `SIGINT`/`SIGTERM` beenden den Loop sauber mit Exit-Code 0.
- `restart: on-failure` startet den Container nach einem echten Fehler neu.

## 4. Backup

- `BACKUP=true` kopiert die Eingabedatei vor der Verarbeitung nach `BACKUP_DIR`.
- Relative Pfade bleiben erhalten.
- Ein bereits identisches Backup wird nicht erneut kopiert.
- Schlägt das Backup fehl, wird die Datei nicht verarbeitet.
- Das Backup ist eine vollständige Dateikopie und kostet Zeit und Speicher.
- Alte Backups werden beim Start eines Durchlaufs gemäß
  `BACKUP_RETENTION_DAYS` gelöscht; im Loop höchstens einmal pro Stunde.
- `0` deaktiviert die Bereinigung.
- `BACKUP=true` erfordert `BACKUP_DIR`; sonst Exit-Code 2.

Im Root-Compose ist `BACKUP=true` in `upstream.env` gesetzt. `BACKUP=false` in
`override.env` oder `.env` schaltet es ab.

## 5. Dateien, Überschreiben, Fehler

- Quelldateien werden nur mit `OVERWRITE_SOURCE_FILE=true` verändert.
- In-Place ohne Backup ist erlaubt, wird aber beim Start und pro Datei gewarnt.
- Vorhandene Zieldateien werden bei `OVERWRITE_EXISTING=false` übersprungen.
- Bei `OVERWRITE_EXISTING=true` wird die alte Ausgabedatei erst nach erfolgreichem
  Schreiben ersetzt.
- Geschrieben wird in eine Temp-Datei im Zielverzeichnis und danach atomar
  umbenannt.
- Fehler einzelner Dateien stoppen den Batch nicht.
- Beschädigte oder nicht lesbare Dateien werden als Dateifehler protokolliert.
- Ohne passende Regeln wird die Datei unverändert kopiert.
- Keine passenden Dateien: Warnung, Exit-Code 0.
- Ausgabeverzeichnisse werden bei Bedarf angelegt.

## 6. Logging und Exit-Codes

Pro Datei wird der Name einmal geloggt; Tag-Änderungen erscheinen als Tabelle:

```text
  Tag         | Old Value | New Value
  ------------+-----------+----------
  series      | <leer>    | Old Album
  series-part | <leer>    | 3
  album       | Old Album | Old Title
```

Leere Werte werden als `<leer>` dargestellt. Zusätzlich werden Zeiten für Backup,
Kopieren, Tag-Schreiben, Ziel-Rename und Gesamt ausgegeben.

| Code | Bedeutung |
| --- | --- |
| `0` | Erfolg; im Loop-Modus auch normales Beenden per SIGINT/SIGTERM |
| `1` | Mindestens eine Datei konnte nicht verarbeitet werden |
| `2` | Konfigurationsfehler |

## 7. Linux-Permissions

Der Container läuft als non-root mit UID `1000`.

- `m4b_for_AudioBookShelf` und `m4b_backup` müssen für UID 1000 schreibbar sein.
- Werden die Verzeichnisse von Docker als `root` angelegt, kann der Container
  nicht schreiben. Verzeichnisse vorher selbst anlegen und berechtigen:

```bash
mkdir -p m4b_for_AudioBookShelf m4b_backup m4b_from_AudioBookConverter config
sudo chown -R 1000:1000 m4b_for_AudioBookShelf m4b_backup
```

- Same-Dir und In-Place benötigen ein beschreibbares `/data/in`. Das
  Standard-Compose mountet `/data/in` bewusst read-only; dafür muss der Mount
  angepasst werden.
- Der ABS-Container läuft ohne `user:`-Direktive als root. Wenn du ihn mit
  `user: "1000:1000"` betreibst, müssen auch `/config`, `/metadata` und die
  Library für UID 1000 schreibbar sein.

## 8. ABS-Stack

Für Fixer + Audiobookshelf als einen Stack:

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

Der Fixer schreibt nach `data/out`; ABS mountet genau diesen Ordner als
`/audiobooks`. Der Eingangsordner `data/in` wird von ABS nicht gesehen.

### ABS-Scan

ABS erkennt neue Dateien über **Periodic Scan** oder einen manuellen Scan.
Die ABS-Dokumentation warnt davor, externe Tools mit aktivem „Watch for file
changes“ auf dieselbe Library loszulassen. Für diesen Stack gilt daher:

- Library auf `/audiobooks` anlegen.
- „Watch for file changes“ deaktivieren.
- Periodic Scan aktivieren (z. B. alle 15 Minuten) oder manuell scannen.

Ein API-Trigger nach jedem Fixer-Lauf ist **nicht** implementiert. Das wäre ein
separates Feature und kein Bestandteil des Datei-Workflows.

### Ein Ordner pro Buch

ABS erwartet eine Bibliotheksstruktur mit einem Ordner pro Buch. Im Beispielstack
ist deshalb `REPLICATE_SOURCE_DIR_STRUCTURE=true` gesetzt. Wenn die Eingabe schon
pro Buch in einem Ordner liegt, wird diese Struktur unter `data/out` gespiegelt.

### Nicht direkt in die ABS-Library schreiben

`OVERWRITE_SOURCE_FILE=true` könnte die ABS-Library direkt bearbeiten, ist hier
aber nicht der Standard:

- kein Idempotenz-Marker außer der Datei selbst
- im Loop würde jede Datei bei jedem Durchlauf neu geschrieben
- ABS kann während des Schreibens scannen
- Quelle und Bibliothek wären nicht getrennt

Der Separate-Output-Modus mit `OVERWRITE_EXISTING=false` ist die sichere
Standardvariante.

## 9. Troubleshooting

### ABS zeigt weiterhin falsche Tags

- Prüfe, ob die Library wirklich auf `/audiobooks` (= `data/out`) zeigt und nicht
  auf den Eingangsordner.
- Scanne die Library erneut.
- Prüfe die Datei mit ffprobe:
  ```bash
  ffprobe -v quiet -show_entries format_tags -of json -- "book.m4b"
  ```
- Erwartet: `show` und `episode_id` sind gesetzt.
- Bei `.m4b` sind `mvnm`/`mvin` ohne `-export_all` unsichtbar; das ist normal.

### Datei wird nicht verarbeitet

- `FILENAME_FILTER` prüfen (Default `*.m4b`).
- Bei Unterverzeichnissen: `RECURSIVE=true` oder
  `REPLICATE_SOURCE_DIR_STRUCTURE=true`.
- Bei bereits vorhandener Ausgabe: `OVERWRITE_EXISTING=true` oder Zieldatei
  entfernen.
- Bei Dateien mit `RENAME_SUFFIX`: `SKIP_SUFFIX=true` überspringt sie bewusst.

### Permission denied

- Ausgabe- und Backup-Verzeichnis für UID 1000 schreibbar machen.
- Same-Dir/In-Place: `/data/in` muss beschreibbar sein; Standard-Compose ist
  read-only.

### ABS erkennt neue Bücher nicht

- Periodic Scan aktivieren oder manuell scannen.
- File Watcher nur nutzen, wenn du die ABS-Warnung zu externen Tools akzeptierst.
- Prüfen, ob die Datei tatsächlich in `data/out` liegt.

### Keine oder falsche Seriennummer

- `series-part` muss eine Ganzzahl sein.
- `tvsh`/`tven` haben beim Lesen Vorrang vor `mvnm`/`mvin`.
- Default-Mapping nur bei AudioBookConverter-Quellen verwenden.

### Docker-Compose-Fehler zu `env_file`

`env_file.required` benötigt Compose ≥ 2.24. Ältere Versionen brechen mit einem
Schema-Fehler ab.

## 10. Sicherheit

- `.env` und `override.env` nicht committen.
- Backups enthalten vollständige Hörbücher; Zugriff entsprechend schützen.
- ABS nicht ungeschützt ins Internet stellen; VPN oder Reverse Proxy verwenden.
- Der Fixer benötigt keine Netzwerkverbindung und keinen ABS-API-Token.

## 11. GHCR

`.github/workflows/docker.yml` baut und pusht
`ghcr.io/yasuoiwakura/audiobook-tag-rewriter`:

- Push auf `main`, `dev`, `test`
- veröffentlichte Releases
- manueller `workflow_dispatch`

Tags: `latest` für `main`, Branch-Namen, Commit-SHA, Branch-SHA und Release-Tags.
Optional kann `vars.DOCKER_SHORT_NAME` einen zweiten GHCR-Image-Namen aktivieren.

## 12. Weiterführend

- [`CONFIGURATION.md`](CONFIGURATION.md) – alle Optionen
- [`ARCHITECTURE.md`](ARCHITECTURE.md) – technischer Ablauf
- [`../examples/abs/README.md`](../examples/abs/README.md) – ABS-Stack
