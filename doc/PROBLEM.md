# Problem: Falscher Audiobookshelf-Import von AudioBookConverter-M4Bs

Status: dokumentiert; Workaround implementiert  
Stand: 2026-10-21

## 1. Kurzfassung

AudioBookConverter schreibt Serienhörbücher mit einer anderen Tag-Semantik, als
Audiobookshelf (ABS) bei M4B-Dateien erwartet:

- `album` = Serie
- `track` = Seriennummer
- `title` = Buchtitel

Audiobookshelf verwendet bei M4B dagegen `album` als Buchtitel und `track` als
Track/Kapitel. Serie und Seriennummer wertet der ffprobe-basierte Scanner nur
über `show` und `episode_id` aus, die aus den MP4-Atomen `tvsh` und `tven`
stammen.

Das allein wäre lösbar, indem man `mvnm`/`mvin` schreibt. ABS ruft ffprobe aber
ohne `-export_all` auf. Dadurch sind `mvnm`/`mvin` bei MP4/M4B für ABS unsichtbar.
Ergebnis: Der Buchtitel landet im falschen Feld, Serie und Seriennummer bleiben
leer.

## 2. Symptome

Nach dem Import einer betroffenen `.m4b`-Datei in Audiobookshelf:

- Der Buchtitel ist leer oder entspricht dem Album-/Seriennamen.
- Die Serie ist leer.
- Die Seriennummer (Series Sequence) ist leer.
- `track` wird als Kapitel/Track angezeigt, obwohl es die Seriennummer ist.
- Die Datei muss manuell in ABS nachbearbeitet werden.

## 3. Ursachenkette

1. **AudioBookConverter-Tag-Semantik**
   - `album = Serie`
   - `track = Seriennummer`
   - `title = Buchtitel`

2. **Audiobookshelf-Mapping für M4B**
   - `album` → Buchtitel
   - `track` → Track/Kapitel
   - `show` → Serie
   - `episode_id` → Seriennummer

3. **ffprobe-Verhalten bei MP4/M4B**
   - `tvsh`/`tven` werden als `show`/`episode_id` exportiert und sind für ABS
     sichtbar.
   - `mvnm`/`mvin` sind für den MOV/MP4-Demuxer unbekannte Atome.
   - Ohne `-export_all` erscheinen sie nicht in `format.tags`.

4. **Folge**
   - Die dokumentierte ABS-Zuordnung `mvnm`/`mvin` greift bei M4B nicht.
   - Die vorhandenen Werte aus `album`/`track` werden falsch interpretiert.

## 4. Nachweis

Der Upstream-Issue-Entwurf [`ABS-issue-readtags.md`](../ABS-issue-readtags.md)
enthält die vollständigen ffprobe-Beispiele. Kurzfassung:

```powershell
# Ohne -export_all: mvnm/mvin fehlen
ffprobe.exe -v quiet -show_entries format_tags -of json -- "file.m4b"

# Mit -export_all: mvnm/mvin sind sichtbar
ffprobe.exe -v quiet -export_all 1 -show_entries format_tags -of json -- "file.m4b"
```

Beispielausgabe mit `-export_all`:

```json
{
  "format": {
    "tags": {
      "title": "Ein Scheck über eine Milliarde (Ungekürzt)",
      "artist": "Vasily Mahanenko",
      "album": "Ein Scheck über eine Milliarde (Ungekürzt)",
      "track": "3",
      "mvin": "3",
      "mvnm": "Galaktogon"
    }
  }
}
```

Relevante ABS-Quellen:

- `server/libs/nodeFfprobe/index.js` (ffprobe-Aufruf ohne `-export_all`)
- `server/utils/prober.js` (Mapping `series/show/mvnm`, `series-part/episode_id/mvin`)
- `server/scanner/AudioFileScanner.js`

## 5. Entscheidung

Der Fix erfolgt **auf Dateiebene in einer Kopie**, nicht durch Patchen von ABS:

- `album` wird nach `series` kopiert und als `tvsh` + `mvnm` geschrieben.
- `track` wird nach `series-part` kopiert und als `tven` + `mvin` geschrieben.
- Anschließend wird `album` auf `title` gesetzt.

Damit funktionieren beide Welten:

- `tvsh`/`tven` sind für ABS und ffprobe ohne `-export_all` sichtbar.
- `mvnm`/`mvin` bleiben für andere Player (Plex, Apple ecosystem usw.) erhalten.

Die Quelldatei bleibt im Standardmodus unverändert. Das In-Place-Überschreiben
ist eine separate, explizit zu aktivierende Option.

## 6. Verworfene Alternativen

| Alternative | Warum nicht |
| --- | --- |
| ABS patchen oder forken | Wartungsaufwand, Upstream-Konflikt, betrifft alle Nutzer |
| Nur auf einen Upstream-Fix warten | Blockiert den eigenen Import auf unbestimmte Zeit |
| ABS-Metadaten nach dem Import per API setzen | Nicht dateiportabel, keine Lösung für andere Player |
| Alle Dateien direkt in der ABS-Library überschreiben | Kein Idempotenz-Marker, unnötige Schreiblast, Scan-Rennen |
| `mvnm`/`mvin` allein schreiben | Für ABS bei M4B unsichtbar |

## 7. Scope und Nicht-Scope

**Scope:**

- Batch-Verarbeitung von `.m4b`-Dateien.
- Tag-zu-Tag-Mapping und exakte Wert-Ersetzungen.
- Optional: Backup, Suffix, Same-Dir, rekursive Struktur, In-Place-Overwrite.
- Docker-Betrieb als Sidecar vor einer ABS-Library.

**Nicht-Scope:**

- Re-Encoding oder Remuxing der Audiodaten.
- Bibliotheksverwaltung, Metadaten-Matching oder Cover-Download.
- Direkte Manipulation der ABS-Datenbank.
- Garantierte korrekte Ergebnisse für Nicht-AudioBookConverter-Quellen.
- Automatisches Löschen oder Verschieben der Quelldateien.

## 8. Grenzen und Risiken

- **Vollkopie:** Jede verarbeitete Datei wird vollständig kopiert, auch wenn sich
  keine Tags ändern. Bei großen M4Bs kostet das Zeit und Speicher.
- **MP4-Layout:** Bei `moov` vor `mdat` kann eine Tag-Vergrößerung den
  `mdat`-Block verschieben.
- **Quellannahme:** Das Default-Mapping ist auf die in den Issues beschriebenen
  AudioBookConverter-Dateien ausgelegt. Andere Quellen brauchen ein eigenes
  `TAG_MAP`.
- **Upstream offen:** Der ffprobe/`-export_all`-Fix liegt bei Audiobookshelf.
  Dieses Projekt ist ein Workaround, keine Upstream-Lösung.
- **Kein ABS-Integrationstest:** Die Tests verwenden synthetische M4B-Dateien.
  Ein echter ABS-Scan ist kein automatisierter Bestandteil der Testsuite.

## 9. Upstream

- [`ABS-issue-readtags.md`](../ABS-issue-readtags.md) – Entwurf für das
  Audiobookshelf-Issue (englisch).
- [AudioBookConverter #759](https://github.com/yermak/AudioBookConverter/issues/759)
- [Audiobookshelf #5669](https://github.com/advplyr/audiobookshelf/issues/5669)
- [Audiobookshelf #2471](https://github.com/advplyr/audiobookshelf/issues/2471)

## 10. Referenzen

- [Audiobookshelf: Book Library Structure](https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/)
- [Audiobookshelf: Docker-Installation](https://audiobookshelf.org/docs/documentation/install/docker/)
- [`SPEC.md`](../SPEC.md) – Implementierungsstand und Abnahmekriterien
- [`ARCHITECTURE.md`](ARCHITECTURE.md) – technischer Ablauf
- [`CONFIGURATION.md`](CONFIGURATION.md) – alle Optionen
- [`OPERATIONS.md`](OPERATIONS.md) – Betrieb und Troubleshooting
