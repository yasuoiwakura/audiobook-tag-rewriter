from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import Config
from .metadata import (
    MetadataError,
    TagReportEntry,
    TagSnapshot,
    apply_mapping,
    apply_rule,
    build_tag_report,
    format_tags,
    read_tags,
    write_changes,
)

FileStatus = Literal["processed", "skipped", "failed"]

BACKUP_CLEANUP_INTERVAL_SECONDS = 3600


@dataclass(frozen=True)
class TagChange:
    tag: str
    old: str
    new: str


@dataclass(frozen=True)
class FileOutcome:
    status: FileStatus
    changes: int = 0
    message: str = ""
    backed_up: bool = False


@dataclass
class Summary:
    found: int = 0
    processed: int = 0
    skipped: int = 0
    changes: int = 0
    failed: int = 0
    backups: int = 0
    backups_deleted: int = 0
    cleanup_seconds: float = 0.0


def _display_values(values: tuple[str, ...] | list[str]) -> str:
    text = ", ".join(values) if values else ""
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text or "<leer>"


class BatchProcessor:
    def __init__(self, config: Config, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._last_cleanup: float | None = None

    def _matches_filter(self, filename: str) -> bool:
        return fnmatch.fnmatchcase(
            filename.casefold(), self.config.filename_filter.casefold()
        )

    def discover_files(self) -> list[Path]:
        if self.config.single_file is not None:
            return [self.config.single_file]

        base = self.config.input_dir
        iterator = (
            base.rglob("*") if self.config.scans_recursively else base.iterdir()
        )
        files = [
            path
            for path in iterator
            if path.is_file()
            and path.suffix.lower() == ".m4b"
            and self._matches_filter(path.name)
            and not self._has_processed_suffix(path)
        ]
        return sorted(files, key=lambda path: str(path).casefold())

    def _has_processed_suffix(self, path: Path) -> bool:
        suffix = self.config.rename_suffix
        return bool(
            self.config.skip_suffix
            and suffix
            and path.stem.casefold().endswith(suffix.casefold())
        )

    def _target_name(self, source: Path) -> str:
        suffix = self.config.rename_suffix
        if not suffix or source.stem.casefold().endswith(suffix.casefold()):
            return source.name
        return f"{source.stem} {suffix}{source.suffix}"

    def _base_output_path(self, source: Path) -> Path:
        if self.config.output_same_dir:
            return source.parent / source.name
        if self.config.single_file is not None:
            return self.config.output_dir / source.name
        if self.config.scans_recursively:
            relative = source.relative_to(self.config.input_dir)
            return self.config.output_dir / relative
        return self.config.output_dir / source.name

    def output_path_for(self, source: Path) -> Path:
        base = self._base_output_path(source)
        same_as_source = base.resolve() == source.resolve()
        apply_suffix = self.config.output_suffix or (
            same_as_source and not self.config.overwrite_source_file
        )
        if apply_suffix:
            return base.with_name(self._target_name(base))
        return base

    def run(self) -> Summary:
        files = self.discover_files()
        summary = Summary(found=len(files))
        deleted, cleanup_seconds = self._cleanup_backups_if_due()
        summary.backups_deleted = deleted
        summary.cleanup_seconds = cleanup_seconds

        if files:
            log = self.logger.debug if self.config.loop else self.logger.info
            log("Gefundene .m4b-Dateien: %d", summary.found)
        else:
            if self.config.loop:
                self.logger.debug(
                    "Keine passenden .m4b-Dateien in %s gefunden.",
                    self.config.input_dir,
                )
            else:
                self.logger.warning(
                    "Keine passenden .m4b-Dateien in %s gefunden.",
                    self.config.input_dir,
                )
            return summary

        for source in files:
            try:
                outcome = self.process_file(source)
            except Exception:
                self.logger.exception("Unerwarteter Fehler bei %s", source)
                outcome = FileOutcome(status="failed", message="unexpected error")

            if outcome.status == "processed":
                summary.processed += 1
                summary.changes += outcome.changes
                if outcome.backed_up:
                    summary.backups += 1
            elif outcome.status == "skipped":
                summary.skipped += 1
            else:
                summary.failed += 1

        return summary

    def process_file(self, source: Path) -> FileOutcome:
        output = self.output_path_for(source)
        in_place = output.resolve() == source.resolve()

        if in_place:
            if not self.config.overwrite_source_file:
                message = (
                    "Ausgabepfad ist identisch mit der Quelldatei; "
                    "OVERWRITE_SOURCE_FILE ist deaktiviert."
                )
                self.logger.error("%s: %s", source, message)
                return FileOutcome(status="failed", message=message)
        else:
            if output.is_dir():
                message = f"Ausgabepfad ist ein Verzeichnis: {output}"
                self.logger.error("%s: %s", source, message)
                return FileOutcome(status="failed", message=message)

            if output.exists():
                if not self.config.overwrite_existing:
                    message = f"Ausgabedatei existiert bereits, wird übersprungen: {output}"
                    log = self.logger.debug if self.config.loop else self.logger.warning
                    log("%s: %s", source, message)
                    return FileOutcome(status="skipped", message=message)
                self.logger.warning(
                    "%s: Ausgabedatei wird überschrieben: %s", source, output
                )

        if in_place:
            if self.config.backup:
                self.logger.warning(
                    "%s: Quelle wird überschrieben "
                    "(OVERWRITE_SOURCE_FILE=true, Backup aktiv).",
                    source,
                )
            else:
                self.logger.warning(
                    "%s: WARNUNG: Quelle wird OHNE Backup überschrieben "
                    "(BACKUP=false).",
                    source,
                )
        self.logger.info("Datei: %s", source)
        total_start = time.perf_counter()

        try:
            backed_up, backup_seconds = self._backup_source(source)
        except (OSError, MetadataError) as exc:
            self.logger.error("%s: Backup fehlgeschlagen: %s", source, exc)
            return FileOutcome(status="failed", message=str(exc))

        try:
            snapshot = read_tags(source)
        except MetadataError as exc:
            self.logger.error("%s: %s", source, exc)
            return FileOutcome(status="failed", message=str(exc))

        self.logger.debug("%s: Tags: %s", source.name, format_tags(snapshot))
        before = snapshot.clone()

        changes: list[TagChange] = []
        changed_fields: set[str] = set()

        for mapping in self.config.tag_mappings:
            result = apply_mapping(snapshot, mapping.source, mapping.target)
            if result.status == "changed":
                changed_fields.add(mapping.target)
                changes.append(
                    TagChange(
                        tag=result.target,
                        old=_display_values(result.previous_target),
                        new=_display_values(result.values),
                    )
                )
                self.logger.debug(
                    "%s: Mapping '%s' -> '%s': %s (vorher: %s)",
                    source.name,
                    result.source,
                    result.target,
                    _display_values(result.values),
                    _display_values(result.previous_target),
                )
            elif result.status == "missing":
                self.logger.debug(
                    "%s: Mapping '%s' -> '%s': Quelltag nicht gesetzt; übersprungen.",
                    source.name,
                    result.source,
                    result.target,
                )
            elif result.status == "same_field":
                self.logger.debug(
                    "%s: Mapping '%s' -> '%s': Quelle und Ziel sind identisch; übersprungen.",
                    source.name,
                    result.source,
                    result.target,
                )
            else:
                self.logger.debug(
                    "%s: Mapping '%s' -> '%s': Ziel hat bereits den Wert %s; unverändert.",
                    source.name,
                    result.source,
                    result.target,
                    _display_values(result.values),
                )

        for rule in self.config.tag_rules:
            result = apply_rule(snapshot, rule.tag, rule.old, rule.new)
            if result.status == "changed":
                changed_fields.add(rule.tag)
                changes.append(
                    TagChange(
                        tag=rule.tag,
                        old=_display_values([rule.old]),
                        new=_display_values([rule.new]),
                    )
                )
                self.logger.debug(
                    "%s: Tag '%s' geändert: %s -> %s (%d Wert(e))",
                    source.name,
                    rule.tag,
                    rule.old,
                    rule.new,
                    result.replaced,
                )
            elif result.status == "missing":
                self.logger.debug(
                    "%s: Tag '%s' ist nicht gesetzt; Regel %r -> %r nicht angewendet.",
                    source.name,
                    rule.tag,
                    rule.old,
                    rule.new,
                )
            else:
                self.logger.debug(
                    "%s: Tag '%s' hat den Wert %r statt %r; Regel nicht angewendet.",
                    source.name,
                    rule.tag,
                    ", ".join(result.current),
                    rule.old,
                )

        try:
            copy_seconds, tag_seconds, target_seconds = self._copy_and_write(
                source, output, snapshot, changed_fields
            )
        except (OSError, MetadataError) as exc:
            self.logger.error("%s: Verarbeitung fehlgeschlagen: %s", source, exc)
            return FileOutcome(status="failed", message=str(exc))

        total_seconds = time.perf_counter() - total_start

        referenced = {mapping.source for mapping in self.config.tag_mappings}
        referenced.update(mapping.target for mapping in self.config.tag_mappings)
        referenced.update(rule.tag for rule in self.config.tag_rules)
        self._log_tag_report(
            build_tag_report(before, snapshot, referenced=referenced)
        )

        self.logger.info(
            "  Zeiten: Backup %.2fs | Kopieren %.2fs | Tags %.2fs | Ziel-Rename %.2fs | Gesamt %.2fs",
            backup_seconds,
            copy_seconds,
            tag_seconds,
            target_seconds,
            total_seconds,
        )
        self.logger.info("  Ausgabe: %s", output)

        return FileOutcome(
            status="processed",
            changes=len(changes),
            backed_up=backed_up,
        )

    def _log_tag_report(self, entries: list[TagReportEntry]) -> None:
        if not entries:
            self.logger.info("  Keine Tags gelesen oder geschrieben.")
            return
        rows = [
            (entry.tag, _display_values(entry.old), _display_values(entry.new))
            for entry in entries
        ]
        self._log_table(("Tag", "Old Value", "New Value"), rows)

    def _log_table(
        self, headers: tuple[str, ...], rows: list[tuple[str, ...]]
    ) -> None:
        table = [headers, *rows]
        widths = [max(len(row[index]) for row in table) for index in range(len(headers))]

        for index, row in enumerate(table):
            if index == 1:
                self.logger.info(
                    "  %s",
                    "-+-".join("-" * width for width in widths),
                )
            self.logger.info(
                "  %s",
                " | ".join(
                    value.ljust(widths[column])
                    for column, value in enumerate(row)
                ),
            )

    def _backup_source(self, source: Path) -> tuple[bool, float]:
        if not self.config.backup:
            return False, 0.0

        start = time.perf_counter()
        backup_dir = self.config.backup_dir
        if backup_dir is None:
            raise MetadataError("BACKUP_DIR ist nicht gesetzt.")

        try:
            relative = source.relative_to(self.config.input_dir)
        except ValueError:
            relative = Path(source.name)

        target = backup_dir / relative
        if target.resolve() == source.resolve():
            raise MetadataError(
                f"Backup-Pfad ist identisch mit der Quelldatei: {target}"
            )

        if target.exists():
            source_stat = source.stat()
            target_stat = target.stat()
            if (
                source_stat.st_size == target_stat.st_size
                and target_stat.st_mtime >= source_stat.st_mtime
            ):
                self.logger.debug(
                    "%s: Backup bereits vorhanden: %s", source.name, target
                )
                return False, time.perf_counter() - start

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        os.close(fd)
        temp_path = Path(temp_name)
        completed = False
        try:
            shutil.copy2(source, temp_path)
            os.utime(temp_path, None)
            os.replace(temp_path, target)
            completed = True
        finally:
            if not completed:
                temp_path.unlink(missing_ok=True)

        self.logger.info("  Backup erstellt: %s", target)
        return True, time.perf_counter() - start

    def _cleanup_backups_if_due(self) -> tuple[int, float]:
        if not self.config.backup or (self.config.backup_retention_days or 0) <= 0:
            return 0, 0.0
        now = time.monotonic()
        if (
            self._last_cleanup is not None
            and now - self._last_cleanup < BACKUP_CLEANUP_INTERVAL_SECONDS
        ):
            return 0, 0.0
        self._last_cleanup = now
        return self._cleanup_old_backups()

    def _cleanup_old_backups(self) -> tuple[int, float]:
        backup_dir = self.config.backup_dir
        retention_days = self.config.backup_retention_days
        if backup_dir is None or retention_days <= 0:
            return 0, 0.0

        start = time.perf_counter()
        cutoff = time.time() - retention_days * 86400
        deleted = 0

        for path in backup_dir.rglob("*"):
            try:
                if (
                    path.is_file()
                    and path.suffix.lower() == ".m4b"
                    and path.stat().st_mtime < cutoff
                ):
                    path.unlink()
                    deleted += 1
            except OSError as exc:
                self.logger.warning("Backup-Cleanup fehlgeschlagen für %s: %s", path, exc)

        elapsed = time.perf_counter() - start
        if deleted:
            self.logger.info(
                "Backup-Bereinigung: %d Datei(en) älter als %d Tage entfernt.",
                deleted,
                retention_days,
            )
        else:
            self.logger.debug(
                "Backup-Bereinigung: keine Dateien älter als %d Tage gefunden.",
                retention_days,
            )
        return deleted, elapsed

    def _copy_and_write(
        self,
        source: Path,
        output: Path,
        snapshot: TagSnapshot,
        changed_fields: set[str],
    ) -> tuple[float, float, float]:
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        os.close(fd)
        temp_path = Path(temp_name)
        completed = False
        copy_seconds = 0.0
        tag_seconds = 0.0
        target_seconds = 0.0
        try:
            copy_start = time.perf_counter()
            shutil.copy2(source, temp_path)
            copy_seconds = time.perf_counter() - copy_start

            tag_start = time.perf_counter()
            write_changes(temp_path, snapshot, changed_fields)
            tag_seconds = time.perf_counter() - tag_start

            target_start = time.perf_counter()
            os.replace(temp_path, output)
            target_seconds = time.perf_counter() - target_start
            completed = True
        finally:
            if not completed:
                temp_path.unlink(missing_ok=True)
        return copy_seconds, tag_seconds, target_seconds
