# Feature-Inventar

Übersicht aller geplanten, in Umsetzung befindlichen und umgesetzten Features.
Jedes Feature besitzt ein eigenes Dokument in diesem Verzeichnis.

## Konventionen

- Branch: `matt-nnnn`, fortlaufend, z. B. `matt-0004`
- Feature-Datei: `feat-nnnn-kebab-case-titel.md`; `nnnn` entspricht der Branch-Nummer
  (z. B. `feat-0004-replicate-source-dir-structure.md`)
- Titel im Dokument: `# feat-nnnn – Titel`
- Statuswerte: `geplant`, `in Umsetzung`, `umgesetzt`, `verworfen`
- Jedes Dokument enthält: Ziel, Konfiguration, Verhalten, Akzeptanzkriterien,
  Tests, Dokumentation
- Implementierte Features werden zusätzlich in `SPEC.md`, `README.md` sowie
  `doc/CONFIGURATION.md` und `doc/OPERATIONS.md` geführt

## Inventar

| Feature | Branch | Status | Konfiguration | Kurzbeschreibung |
| --- | --- | --- | --- | --- |
| [feat-0004](feat-0004-replicate-source-dir-structure.md) | `matt-0004` | umgesetzt | `REPLICATE_SOURCE_DIR_STRUCTURE` (Env, YAML, CLI) | Dateien rekursiv finden und im Zielverzeichnis in der entsprechenden Unterverzeichnisstruktur ablegen; Default `false` |
| [feat-0005](feat-0005-output-suffix-and-overwrite-source.md) | `matt-0005` | umgesetzt | `OUTPUT_SUFFIX`, `OVERWRITE_SOURCE_FILE` (Env, YAML, CLI) | Suffix explizit anwenden bzw. nur als Overwrite-Schutz; Quelle optional in-place überschreiben (`BACKUP=true` dringend empfohlen); Defaults `false` |
