from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from . import __version__
from .config import (
    DEFAULT_MAPPING_DESCRIPTION,
    Config,
    ConfigError,
    load_config,
    load_file_config,
)
from .processor import BatchProcessor, Summary

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
logger = logging.getLogger("m4b_tag_fixer")


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger().setLevel(level)


def _log_summary(summary: Summary) -> None:
    logger.info("Zusammenfassung:")
    logger.info("  Gefundene Dateien:            %d", summary.found)
    logger.info("  Verarbeitete Dateien:         %d", summary.processed)
    logger.info("  Übersprungene Dateien:        %d", summary.skipped)
    logger.info("  Erfolgreiche Tag-Änderungen:  %d", summary.changes)
    logger.info("  Erstellte Backups:            %d", summary.backups)
    if summary.backups_deleted:
        logger.info("  Gelöschte Backups:            %d", summary.backups_deleted)
        logger.info("  Backup-Cleanup:               %.2f s", summary.cleanup_seconds)
    logger.info("  Fehlgeschlagene Dateien:      %d", summary.failed)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m4b-tag-fixer",
        description="Ersetzt und mappt MP4-Metadaten in .m4b-Hörbuchdateien.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional: genau diese .m4b-Datei verarbeiten (statt INPUT_DIR zu durchsuchen).",
    )
    parser.add_argument("--input-dir", help="Eingabeverzeichnis (Default: /in).")
    parser.add_argument("--output-dir", help="Ausgabeverzeichnis (Default: /out).")
    parser.add_argument(
        "--filename-filter", help="Glob-Muster für Dateinamen (Default: *.m4b)."
    )
    parser.add_argument(
        "--tag-rules",
        help='JSON-Liste von Wert-Ersetzungen, z. B. [{"tag":"album","old":"A","new":"B"}].',
    )
    parser.add_argument(
        "--tag-map",
        help='JSON-Liste von Tag-Mappings, z. B. [{"from":"album","to":"series"}].',
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Unterverzeichnisse einbeziehen (--recursive / --no-recursive).",
    )
    parser.add_argument(
        "--replicate-source-dir-structure",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Unterverzeichnisse rekursiv durchsuchen und die Struktur unter "
            "OUTPUT_DIR nachbilden."
        ),
    )
    parser.add_argument(
        "--overwrite-existing",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Vorhandene Ausgabedateien überschreiben.",
    )
    parser.add_argument(
        "--same-dir",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Kopie im Quellordner mit RENAME_SUFFIX ablegen (Quelle bleibt unverändert).",
    )
    parser.add_argument(
        "--rename-suffix",
        help="Suffix für Ausgabedateien (Default: [TAGS_REMAPPED]).",
    )
    parser.add_argument(
        "--output-suffix",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="RENAME_SUFFIX immer an Ausgabedateien anhängen.",
    )
    parser.add_argument(
        "--overwrite-source-file",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "WARNUNG: Quelldatei in-place überschreiben. BACKUP=true wird "
            "dringend empfohlen; ohne Backup ist die Änderung unwiderruflich. "
            "Ohne diese Option wird bei einem Zielpfad gleich der Quelle "
            "automatisch der Suffix angehängt."
        ),
    )
    parser.add_argument(
        "--skip-suffix",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Bereits suffixed Dateien überspringen.",
    )
    parser.add_argument(
        "--backup",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Quelldatei vor der Verarbeitung nach BACKUP_DIR sichern.",
    )
    parser.add_argument(
        "--backup-dir",
        help="Zielverzeichnis für Backups; erforderlich bei --backup.",
    )
    parser.add_argument(
        "--backup-retention-days",
        type=int,
        default=None,
        help="Backups älter als N Tage löschen; 0 deaktiviert die Bereinigung.",
    )
    parser.add_argument(
        "--loop",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Dauerhaft als Dienst laufen (--loop / --no-loop).",
    )
    parser.add_argument(
        "--loop-interval",
        type=float,
        default=None,
        help="Sekunden zwischen zwei Loop-Durchläufen (Default: 60).",
    )
    parser.add_argument("--log-level", help="Log-Level, z. B. INFO oder DEBUG.")
    parser.add_argument(
        "--config",
        help="Optionale YAML-Konfigurationsdatei (z. B. config.example.yml).",
    )
    parser.add_argument(
        "--env-file",
        help="Optionale .env-Datei (Default: .env im Arbeitsverzeichnis).",
    )
    parser.add_argument(
        "--version", action="version", version=f"m4b-tag-fixer {__version__}"
    )
    return parser


def _load_dotenv(explicit: str | None) -> Path | None:
    raw = explicit or os.environ.get("ENV_FILE") or ".env"
    path = Path(raw).expanduser()
    explicit_requested = bool(explicit) or bool(os.environ.get("ENV_FILE"))
    if path.is_file():
        load_dotenv(path, override=False)
        return path
    if explicit_requested:
        raise ConfigError(f"ENV_FILE wurde nicht gefunden: {path}")
    return None


def _resolve_config_file(explicit: str | None) -> Path | None:
    raw = explicit or os.environ.get("CONFIG_FILE")
    if not raw or not raw.strip():
        return None
    return Path(raw.strip()).expanduser()


def _overrides_from_args(args: argparse.Namespace) -> dict[str, object]:
    return {
        "INPUT_DIR": args.input_dir,
        "OUTPUT_DIR": args.output_dir,
        "FILENAME_FILTER": args.filename_filter,
        "TAG_RULES": args.tag_rules,
        "TAG_MAP": args.tag_map,
        "RECURSIVE": args.recursive,
        "REPLICATE_SOURCE_DIR_STRUCTURE": args.replicate_source_dir_structure,
        "OVERWRITE_EXISTING": args.overwrite_existing,
        "OUTPUT_SAME_DIR": args.same_dir,
        "RENAME_SUFFIX": args.rename_suffix,
        "OUTPUT_SUFFIX": args.output_suffix,
        "OVERWRITE_SOURCE_FILE": args.overwrite_source_file,
        "SKIP_SUFFIX": args.skip_suffix,
        "BACKUP": args.backup,
        "BACKUP_DIR": args.backup_dir,
        "BACKUP_RETENTION_DAYS": args.backup_retention_days,
        "LOOP": args.loop,
        "LOOP_INTERVAL": args.loop_interval,
        "LOG_LEVEL": args.log_level,
        "SINGLE_FILE": args.file,
    }


def _run_once(config: Config) -> int:
    summary = BatchProcessor(config, logger).run()
    _log_summary(summary)
    if summary.failed:
        logger.error(
            "Verarbeitung mit %d fehlgeschlagenen Datei(en) beendet.",
            summary.failed,
        )
        return 1
    logger.info("Verarbeitung erfolgreich abgeschlossen.")
    return 0


def _has_activity(summary: Summary) -> bool:
    return bool(
        summary.processed
        or summary.changes
        or summary.failed
        or summary.backups
        or summary.backups_deleted
    )


def _run_loop(config: Config, stop_event: threading.Event | None = None) -> int:
    processor = BatchProcessor(config, logger)
    stop = stop_event or threading.Event()

    def handle_signal(signum, _frame) -> None:
        logger.info("Stop-Signal %s erhalten; Loop wird beendet.", signum)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_signal)
        except (OSError, ValueError):
            pass

    logger.info("Loop-Modus aktiv (Intervall: %.0f s).", config.loop_interval)
    while not stop.is_set():
        try:
            summary = processor.run()
            if _has_activity(summary):
                _log_summary(summary)
            else:
                logger.debug("Leerlauf: keine Verarbeitung in diesem Durchlauf.")
        except Exception:
            logger.exception("Loop-Durchlauf fehlgeschlagen")
        logger.debug(
            "Nächster Durchlauf in %.0f Sekunde(n) ...", config.loop_interval
        )
        stop.wait(config.loop_interval)

    logger.info("Loop beendet.")
    return 0


def _log_start(config: Config, dotenv_path: Path | None, config_path: Path | None) -> None:
    logger.info("m4b-tag-fixer %s", __version__)
    if dotenv_path is not None:
        logger.info(".env geladen: %s", dotenv_path)
    if config_path is not None:
        logger.info("YAML-Konfiguration: %s", config_path)
    logger.info("Ausgabe:       %s", config.output_dir)
    if config.single_file is not None:
        logger.info("Einzeldatei:   %s", config.single_file)
    else:
        logger.info("Eingabe:       %s", config.input_dir)
        logger.info("Filter:        %s", config.filename_filter)
        logger.info("Rekursiv (RECURSIVE): %s", config.recursive)
        logger.info("Suche rekursiv: %s", config.scans_recursively)
        logger.info("Struktur spiegeln: %s", config.replicate_source_dir_structure)
    logger.info("Loop:          %s", config.loop)
    logger.info("Überschreiben: %s", config.overwrite_existing)
    logger.info("Quelle überschreiben: %s", config.overwrite_source_file)
    logger.info("Gleicher Ordner: %s", config.output_same_dir)
    logger.info("Suffix anwenden: %s", config.output_suffix)
    logger.info("Suffix-Text:   %s", config.rename_suffix or "<keiner>")
    logger.info("Skip-Suffix:   %s", config.skip_suffix)
    logger.info("Backup:        %s", config.backup)
    if config.backup:
        logger.info("Backup-Ziel:   %s", config.backup_dir)
        logger.info("Backup-TTL:    %d Tag(e)", config.backup_retention_days)
    if config.overwrite_source_file and not config.backup:
        logger.warning(
            "WARNUNG: OVERWRITE_SOURCE_FILE=true ohne BACKUP=true; "
            "es wird keine Sicherung erstellt."
        )
    logger.info("Mappings:      %d", len(config.tag_mappings))
    if config.used_default_mappings:
        logger.info(
            "Kein TAG_MAP/TAG_RULES angegeben; Default-Mapping aus den Issues: %s",
            DEFAULT_MAPPING_DESCRIPTION,
        )
    logger.info("Ersetzungen:   %d", len(config.tag_rules))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging("INFO")

    try:
        dotenv_path = _load_dotenv(args.env_file)
        config_path = _resolve_config_file(args.config)
        file_config = load_file_config(config_path) if config_path is not None else {}
        config = load_config(
            overrides=_overrides_from_args(args), file_config=file_config
        )
    except ConfigError as exc:
        logger.error("Konfigurationsfehler: %s", exc)
        return 2

    _configure_logging(config.log_level)
    _log_start(config, dotenv_path, config_path)

    if config.loop:
        return _run_loop(config)
    return _run_once(config)


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
