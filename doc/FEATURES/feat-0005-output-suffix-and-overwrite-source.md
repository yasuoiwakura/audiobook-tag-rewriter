# feat-0005 – Output-Suffix und Source-Overwrite

Status: umgesetzt  
Betroffene Variante: `m4b-tag-fixer`  
Defaults: `OUTPUT_SUFFIX=false`, `OVERWRITE_SOURCE_FILE=false`

## 1. Ziel

Suffix-Verhalten und das Überschreiben der Quelle werden von der
Verzeichnisstruktur entkoppelt:

- `OUTPUT_SUFFIX` steuert ausschließlich, ob `RENAME_SUFFIX` an Ausgabedateien
  angehängt wird.
- `OVERWRITE_SOURCE_FILE` erlaubt das In-Place-Überschreiben der Quelle.
- Ohne Overwrite-Freigabe wird der Suffix automatisch nur dann angehängt, wenn
  der Zielpfad sonst identisch mit der Quelle wäre.

`REPLICATE_SOURCE_DIR_STRUCTURE=true` impliziert **kein** `OUTPUT_SUFFIX=true`.

## 2. Konfiguration

| Weg | `OUTPUT_SUFFIX` | `OVERWRITE_SOURCE_FILE` |
| --- | --- | --- |
| Environment / `.env` | `OUTPUT_SUFFIX=true` | `OVERWRITE_SOURCE_FILE=true` |
| YAML | `output_suffix: true` | `overwrite_source_file: true` |
| CLI | `--output-suffix` / `--no-output-suffix` | `--overwrite-source-file` / `--no-overwrite-source-file` |

`RENAME_SUFFIX` bleibt der Suffix-Text (Default `[TAGS_REMAPPED]`).

Präzedenz wie bisher: Defaults < YAML < `.env`/Env < CLI.

## 3. Verhalten

### 3.1 Zielpfad

```text
base = Zielpfad ohne Suffix
       same-dir   -> source
       replicate  -> OUTPUT_DIR / relative(source, INPUT_DIR)
       flat       -> OUTPUT_DIR / source.name

target = base
if OUTPUT_SUFFIX:
    target = mit_suffix(base)                     # immer
elif base == source and not OVERWRITE_SOURCE_FILE:
    target = mit_suffix(base)                     # Schutz vor Overwrite
```

`mit_suffix` hängt den Suffix nicht doppelt an, wenn der Basisname bereits damit
endet.

### 3.2 Matrix

| Modus | `OUTPUT_SUFFIX` | `OVERWRITE_SOURCE_FILE` | Ergebnis |
| --- | --- | --- | --- |
| Same-Dir | `false` | `false` | `book [TAGS_REMAPPED].m4b` |
| Same-Dir | `false` | `true` | Quelle wird in-place überschrieben |
| Same-Dir | `true` | egal | `book [TAGS_REMAPPED].m4b`, Quelle unverändert |
| Replicate/Recursive | `false` | egal | `out/sub/book.m4b` |
| Replicate/Recursive | `true` | egal | `out/sub/book [TAGS_REMAPPED].m4b` |
| Flach | `false` | egal | `out/book.m4b` |
| Flach | `true` | egal | `out/book [TAGS_REMAPPED].m4b` |

### 3.3 In-Place-Overwrite

- Nur wenn `target == source` und `OVERWRITE_SOURCE_FILE=true`.
- `OUTPUT_SUFFIX=true` hat Vorrang: Es entsteht eine Kopie mit Suffix, die Quelle
  bleibt unverändert.
- `BACKUP=true` wird dringend empfohlen. Ohne Backup läuft die Verarbeitung
  trotzdem; pro Datei wird eine Warnung geloggt und es wird nichts gesichert.
- Die Quelldatei wird vorher gesichert, gelesen und über eine Temp-Datei im
  Quellverzeichnis atomar ersetzt.
- Im Loop-Modus wird eine in-place verarbeitete Datei bei jedem Durchlauf erneut
  verarbeitet.

### 3.4 Validierung

- `OVERWRITE_SOURCE_FILE=true` ohne `BACKUP=true` ist erlaubt, wird aber beim
  Start und pro betroffener Datei deutlich gewarnt.
- `OUTPUT_SAME_DIR=true` mit leerem `RENAME_SUFFIX` nur zulässig, wenn
  `OVERWRITE_SOURCE_FILE=true`.
- Ein leerer Suffix bei erzwungenem Overwrite-Schutz (Ziel == Quelle, kein
  Overwrite erlaubt) führt zu einem Dateifehler.
- `OUTPUT_DIR == INPUT_DIR` bleibt verboten.

### 3.5 Logging

- Beim Start: `Suffix anwenden`, `Suffix-Text`, `Quelle überschreiben`.
- `Rekursiv (RECURSIVE)` zeigt den tatsächlichen Variablenwert;
  `Suche rekursiv` zeigt den effektiven Zustand inklusive Replicate.
- In-Place-Overwrites werden pro Datei als Warnung geloggt.

## 4. Akzeptanzkriterien

1. `OUTPUT_SUFFIX=true` hängt den Suffix in jedem Modus an.
2. `OUTPUT_SUFFIX=false` hängt den Suffix nur bei sonst identischem Zielpfad an.
3. Replicate hängt ohne `OUTPUT_SUFFIX` keinen Suffix an.
4. Same-Dir hängt ohne Overwrite-Freigabe automatisch den Suffix an.
5. `OVERWRITE_SOURCE_FILE=true` schreibt die Quelle in-place und erstellt vorher
   ein Backup.
6. Ohne Backup ist der In-Place-Modus erlaubt, wird aber beim Start und pro Datei
   deutlich gewarnt.
7. `OUTPUT_SUFFIX=true` erzeugt auch bei erlaubtem Overwrite eine Kopie.

## 5. Tests

- Config: Defaults, Env/YAML/CLI-Parsing, `OVERWRITE_SOURCE_FILE` ohne Backup
  erlaubt.
- Config: fehlende Backup-Konfiguration erzeugt eine Warnung statt Fehler.
- Config: Same-Dir mit leerem Suffix nur mit Overwrite-Freigabe.
- Processor: Same-Dir in-place inklusive Backup.
- Processor: `OUTPUT_SUFFIX` gewinnt gegen Overwrite-Freigabe.
- Processor: In-Place ohne Backup funktioniert, ändert die Quelle und loggt eine
  Warnung.
- Processor: Replicate mit und ohne `OUTPUT_SUFFIX`.
- Processor: Kollidierender flacher Zielpfad erhält automatisch den Suffix.

## 6. Dokumentation

- `README.md` (Variablen, Suffix-/Overwrite-Abschnitt, Matrix, CLI)
- `SPEC.md` (Implementierungsstand, Variablen, Suffix-Regel)
- `.env.example`, `override.env.example`, `upstream.env`
- `config.example.yml`
- `doc/FEATURES/README.md` (Inventar)
