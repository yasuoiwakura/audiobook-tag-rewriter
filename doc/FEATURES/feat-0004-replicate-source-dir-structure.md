# feat-0004 – Quellverzeichnis-Struktur spiegeln

Status: umgesetzt  
Betroffene Variante: `m4b-tag-fixer`  
Default: `false` (deaktiviert)

## 1. Ziel

Optional soll die Verzeichnisstruktur des Quellverzeichnisses im Zielverzeichnis
nachgebildet werden. Dafür werden Dateien rekursiv im Quellverzeichnis gesucht und
die Ausgabedatei im entsprechenden Unterverzeichnis abgelegt.

Beispiel:

```text
/data/in/German/audiobook.m4b
  -> /data/out/German/audiobook.m4b
```

Das Unterverzeichnis `German` wird also übernommen. Die Datei wird weiterhin nur
kopiert und verändert; die Quelle bleibt unangetastet. Der Dateiname wird durch
dieses Feature nicht verändert; Suffix-Verhalten siehe `feat-0005`.

## 2. Konfiguration

Neue Option, per Default deaktiviert. Sie ist über alle vorhandenen
Konfigurationswege setzbar:

| Weg | Schreibweise |
| --- | --- |
| Environment / `.env` | `REPLICATE_SOURCE_DIR_STRUCTURE=true` |
| YAML | `replicate_source_dir_structure: true` |
| CLI | `--replicate-source-dir-structure` / `--no-replicate-source-dir-structure` |

Präzedenz wie bisher: Defaults < YAML < `.env`/Env < CLI.

Boolesche Werte folgen der bestehenden Logik (`true/false`, `1/0`, `yes/no`,
`on/off`, `ja/nein`).

## 3. Verhalten

### 3.1 Dateisuche

- `REPLICATE_SOURCE_DIR_STRUCTURE=true` impliziert rekursives Suchen
  (`RECURSIVE` muss nicht zusätzlich gesetzt werden).
- Es gelten weiterhin `FILENAME_FILTER`, die `.m4b`-Prüfung und
  `SKIP_SUFFIX`.
- Sortierung bleibt stabil und case-insensitiv.

### 3.2 Ausgabepfad

- Relativer Pfad der Quelldatei zu `INPUT_DIR` wird unter `OUTPUT_DIR`
  nachgebildet.
- Fehlende Unterverzeichnisse werden automatisch erstellt.
- Der Dateiname bleibt unverändert. `OUTPUT_SUFFIX` und
  `OVERWRITE_SOURCE_FILE` sind davon unabhängig (siehe `feat-0005`).

Beispiele:

| `INPUT_DIR` | Quelldatei | `OUTPUT_DIR` | Ergebnis |
| --- | --- | --- | --- |
| `/data/in` | `/data/in/German/audiobook.m4b` | `/data/out` | `/data/out/German/audiobook.m4b` |
| `/data/in` | `/data/in/a/b/book.m4b` | `/data/out` | `/data/out/a/b/book.m4b` |
| `/data/in` | `/data/in/book.m4b` | `/data/out` | `/data/out/book.m4b` |

### 3.3 Interaktion mit bestehenden Optionen

- `OUTPUT_SAME_DIR=true` hat Vorrang: Die Kopie landet weiterhin neben der
  Quelle.
- `SINGLE_FILE` hat Vorrang: Eine explizit übergebene Einzeldatei wird flach
  nach `OUTPUT_DIR` geschrieben.
- `RECURSIVE=true` ohne `REPLICATE_SOURCE_DIR_STRUCTURE` behält das bisherige
  Verhalten (rekursive Suche, Struktur im Ziel, Dateiname ohne zusätzlichen
  Suffix).
- `RECURSIVE=true` zusammen mit `REPLICATE_SOURCE_DIR_STRUCTURE=true` entspricht
  demselben Verhalten; `RECURSIVE` ist dann redundant.
- `OUTPUT_SUFFIX`, `OVERWRITE_SOURCE_FILE`, `OVERWRITE_EXISTING` und
  `SKIP_SUFFIX` gelten unverändert.

### 3.4 Validierung

- Bei aktivierter Option darf `OUTPUT_DIR` nicht innerhalb von `INPUT_DIR`
  liegen (analog zu `RECURSIVE=true`).
- Bei aktivierter Option und `BACKUP=true` darf `BACKUP_DIR` nicht innerhalb von
  `INPUT_DIR` liegen.
- Ungültige boolesche Werte führen zu einem `ConfigError` mit dem Variablennamen.

### 3.5 Logging

- Beim Start wird der aktive Zustand geloggt, z. B.
  `Struktur spiegeln: true`.
- Pro Datei wird weiterhin der tatsächliche Ausgabepfad geloggt.

## 4. Akzeptanzkriterien

1. Default ist `false`; ohne Aktivierung ändert sich kein bestehendes Verhalten.
2. `REPLICATE_SOURCE_DIR_STRUCTURE=true` findet `.m4b`-Dateien auch in
   Unterverzeichnissen.
3. Die Ausgabedatei liegt im gespiegelten Unterverzeichnis unter `OUTPUT_DIR`.
4. Der Dateiname bleibt ohne `OUTPUT_SUFFIX` unverändert.
5. Die Quelle bleibt byte-identisch.
6. `--no-replicate-source-dir-structure` überschreibt `true` aus Env/YAML.
7. Ungültige Werte und unzulässige Verzeichnisüberschneidungen werden mit einem
   verständlichen Konfigurationsfehler abgelehnt.

## 5. Tests

- Config: Default `false`, Env-Parsing, YAML-Key, CLI-Override, ungültiger Wert.
- Config: `OUTPUT_DIR`/`BACKUP_DIR` innerhalb `INPUT_DIR` wird abgelehnt.
- Processor: flaches Verzeichnis wird gespiegelt.
- Processor: mehrere Ebenen (`a/b/book.m4b`) werden gespiegelt.
- Processor: Dateiname bleibt ohne `OUTPUT_SUFFIX` unverändert.
- Processor: `OUTPUT_SUFFIX=true` hängt den Suffix an.
- Processor: bestehendes Ziel wird gemäß `OVERWRITE_EXISTING` übersprungen bzw.
  überschrieben.
- Regression: `RECURSIVE=true` ohne neue Option verhält sich wie bisher.

## 6. Dokumentation

- `README.md` (Variablen-Tabelle, Abschnitt zur Verzeichnisstruktur, CLI-Beispiel)
- `SPEC.md` (Implementierungsstand, Variablen-Tabelle)
- `.env.example`, `override.env.example`, `upstream.env`
- `config.example.yml`
- `doc/FEATURES/feat-0005-output-suffix-and-overwrite-source.md`
