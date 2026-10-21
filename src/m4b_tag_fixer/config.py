from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .metadata import SUPPORTED_TAGS, normalize_tag

DEFAULT_INPUT_DIR = Path("/in")
DEFAULT_OUTPUT_DIR = Path("/out")
DEFAULT_LOOP_INTERVAL = 60.0


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class TagRule:
    tag: str
    old: str
    new: str


@dataclass(frozen=True)
class TagMapping:
    source: str
    target: str


DEFAULT_TAG_MAPPINGS: tuple[TagMapping, ...] = (
    TagMapping(source="album", target="series"),
    TagMapping(source="track", target="series-part"),
    TagMapping(source="title", target="album"),
)

DEFAULT_MAPPING_DESCRIPTION = "album -> series, track -> series-part, title -> album"


@dataclass(frozen=True)
class Config:
    input_dir: Path
    output_dir: Path
    filename_filter: str
    tag_rules: tuple[TagRule, ...]
    tag_mappings: tuple[TagMapping, ...] = ()
    recursive: bool = False
    overwrite_existing: bool = False
    log_level: str = "INFO"
    loop: bool = False
    loop_interval: float = DEFAULT_LOOP_INTERVAL
    single_file: Path | None = None
    used_default_mappings: bool = False
    output_same_dir: bool = False
    rename_suffix: str = "[TAGS_REMAPPED]"
    skip_suffix: bool = True
    backup: bool = False
    backup_dir: Path | None = None
    backup_retention_days: int = 30
    replicate_source_dir_structure: bool = False
    output_suffix: bool = False
    overwrite_source_file: bool = False

    @property
    def scans_recursively(self) -> bool:
        return self.recursive or self.replicate_source_dir_structure


FILE_KEYS = {
    "input_dir",
    "output_dir",
    "filename_filter",
    "tag_rules",
    "tag_map",
    "recursive",
    "overwrite_existing",
    "log_level",
    "loop",
    "loop_interval",
    "single_file",
    "output_same_dir",
    "rename_suffix",
    "skip_suffix",
    "backup",
    "backup_dir",
    "backup_retention_days",
    "replicate_source_dir_structure",
    "output_suffix",
    "overwrite_source_file",
}


def _parse_bool(name: str, raw: str, default: bool) -> bool:
    value = raw.strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on", "ja"}:
        return True
    if value in {"0", "false", "no", "off", "nein"}:
        return False
    raise ConfigError(f"{name} muss ein boolescher Wert sein, erhalten: {raw!r}")


def _as_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _parse_bool(name, value, default=False)
    raise ConfigError(f"{name} muss ein boolescher Wert sein.")


def _as_float(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} muss eine Zahl sein, erhalten: {value!r}") from exc
    if number <= 0:
        raise ConfigError(f"{name} muss größer als 0 sein.")
    return number


def _as_path(name: str, value: Any) -> Path:
    if isinstance(value, Path):
        return value.expanduser()
    if isinstance(value, str) and value.strip():
        return Path(value.strip()).expanduser()
    raise ConfigError(f"{name} muss ein Pfad sein.")


def _parse_log_level(raw: str) -> str:
    value = raw.strip().upper() or "INFO"
    if not isinstance(getattr(logging, value, None), int):
        raise ConfigError(f"LOG_LEVEL ist ungültig: {raw!r}")
    return value


def _decode_json(value: Any, name: str) -> Any:
    if isinstance(value, str):
        if not value.strip():
            raise ConfigError(f"{name} ist leer.")
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{name} ist kein gültiges JSON: {exc}") from exc
    return value


def _parse_rules(value: Any) -> tuple[TagRule, ...]:
    data = _decode_json(value, "TAG_RULES")
    if not isinstance(data, list):
        raise ConfigError("TAG_RULES muss eine JSON-Liste sein.")
    if not data:
        return ()

    rules: list[TagRule] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"TAG_RULES Regel {index} muss ein JSON-Objekt sein.")
        missing = [key for key in ("tag", "old", "new") if key not in item]
        if missing:
            raise ConfigError(
                f"TAG_RULES Regel {index} fehlt(en) Pflichtfeld(er): {', '.join(missing)}"
            )
        values = {key: item[key] for key in ("tag", "old", "new")}
        for key, field_value in values.items():
            if not isinstance(field_value, str):
                raise ConfigError(
                    f"TAG_RULES Regel {index}: Feld {key!r} muss ein String sein."
                )

        tag = normalize_tag(values["tag"])
        if tag not in SUPPORTED_TAGS:
            raise ConfigError(
                f"TAG_RULES Regel {index}: unbekanntes Tag {values['tag']!r}. "
                f"Unterstützt: {', '.join(SUPPORTED_TAGS)}"
            )
        if values["old"] == values["new"]:
            raise ConfigError(
                f"TAG_RULES Regel {index}: old und new sind identisch und bewirken keine Änderung."
            )
        if tag == "track":
            for key in ("old", "new"):
                if not values[key].strip().isdigit():
                    raise ConfigError(
                        f"TAG_RULES Regel {index}: {key} muss für 'track' eine Zahl sein."
                    )

        rules.append(TagRule(tag=tag, old=values["old"], new=values["new"]))

    return tuple(rules)


def _parse_mappings(value: Any) -> tuple[TagMapping, ...]:
    data = _decode_json(value, "TAG_MAP")
    if not isinstance(data, list):
        raise ConfigError("TAG_MAP muss eine JSON-Liste sein.")
    if not data:
        return ()

    mappings: list[TagMapping] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"TAG_MAP Eintrag {index} muss ein JSON-Objekt sein.")
        source = item.get("from", item.get("source"))
        target = item.get("to", item.get("target"))
        if source is None or target is None:
            raise ConfigError(
                f"TAG_MAP Eintrag {index} benötigt 'from' und 'to'."
            )
        if not isinstance(source, str) or not isinstance(target, str):
            raise ConfigError(
                f"TAG_MAP Eintrag {index}: 'from' und 'to' müssen Strings sein."
            )

        source_tag = normalize_tag(source)
        target_tag = normalize_tag(target)
        for original, tag in ((source, source_tag), (target, target_tag)):
            if tag not in SUPPORTED_TAGS:
                raise ConfigError(
                    f"TAG_MAP Eintrag {index}: unbekanntes Tag {original!r}. "
                    f"Unterstützt: {', '.join(SUPPORTED_TAGS)}"
                )
        mappings.append(TagMapping(source=source_tag, target=target_tag))

    return tuple(mappings)


def _lookup(
    name: str,
    file_key: str,
    env: Mapping[str, str],
    overrides: Mapping[str, Any],
    file_config: Mapping[str, Any],
    default: Any,
    *,
    allow_empty: bool = False,
) -> tuple[Any, bool]:
    if overrides.get(name) is not None:
        return overrides[name], True

    env_value = env.get(name)
    if isinstance(env_value, str):
        if env_value.strip() or allow_empty:
            return env_value, True
    elif env_value is not None:
        return env_value, True

    if file_key in file_config:
        file_value = file_config[file_key]
        if isinstance(file_value, str):
            if file_value.strip() or allow_empty:
                return file_value, True
        elif file_value is not None:
            return file_value, True

    return default, False


def load_file_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Konfigurationsdatei existiert nicht: {path}")
    if not path.is_file():
        raise ConfigError(f"Konfigurationsdatei ist keine Datei: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Konfigurationsdatei konnte nicht gelesen werden: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("Die YAML-Konfiguration muss ein Mapping/Objekt sein.")

    normalized: dict[str, Any] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ConfigError("YAML-Konfiguration enthält einen ungültigen Schlüssel.")
        name = key.strip().lower().replace("-", "_")
        if name not in FILE_KEYS:
            raise ConfigError(
                f"Unbekannter YAML-Schlüssel {key!r}. "
                f"Erlaubt: {', '.join(sorted(FILE_KEYS))}"
            )
        normalized[name] = value
    return normalized


def load_config(
    env: Mapping[str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
    file_config: Mapping[str, Any] | None = None,
) -> Config:
    source = os.environ if env is None else env
    cli = overrides or {}
    file_values = file_config or {}

    raw_input, _ = _lookup(
        "INPUT_DIR", "input_dir", source, cli, file_values, DEFAULT_INPUT_DIR
    )
    raw_output, _ = _lookup(
        "OUTPUT_DIR", "output_dir", source, cli, file_values, DEFAULT_OUTPUT_DIR
    )
    raw_single, single_provided = _lookup(
        "SINGLE_FILE", "single_file", source, cli, file_values, None
    )

    input_dir = _as_path("INPUT_DIR", raw_input)
    output_dir = _as_path("OUTPUT_DIR", raw_output)
    single_file = _as_path("SINGLE_FILE", raw_single) if single_provided else None

    if single_file is not None:
        if not single_file.exists():
            raise ConfigError(f"SINGLE_FILE existiert nicht: {single_file}")
        if not single_file.is_file():
            raise ConfigError(f"SINGLE_FILE ist keine Datei: {single_file}")
        if single_file.suffix.lower() != ".m4b":
            raise ConfigError(f"SINGLE_FILE muss eine .m4b-Datei sein: {single_file}")
    else:
        if not input_dir.exists():
            raise ConfigError(f"INPUT_DIR existiert nicht: {input_dir}")
        if not input_dir.is_dir():
            raise ConfigError(f"INPUT_DIR ist kein Verzeichnis: {input_dir}")

    input_resolved = input_dir.resolve()
    output_resolved = output_dir.resolve()
    if input_resolved == output_resolved:
        raise ConfigError("INPUT_DIR und OUTPUT_DIR dürfen nicht identisch sein.")

    raw_filter, _ = _lookup(
        "FILENAME_FILTER", "filename_filter", source, cli, file_values, "*.m4b"
    )
    filename_filter = str(raw_filter).strip() or "*.m4b"

    raw_recursive, _ = _lookup(
        "RECURSIVE", "recursive", source, cli, file_values, False
    )
    recursive = _as_bool("RECURSIVE", raw_recursive)

    raw_replicate, _ = _lookup(
        "REPLICATE_SOURCE_DIR_STRUCTURE",
        "replicate_source_dir_structure",
        source,
        cli,
        file_values,
        False,
    )
    replicate_source_dir_structure = _as_bool(
        "REPLICATE_SOURCE_DIR_STRUCTURE", raw_replicate
    )
    scans_recursively = recursive or replicate_source_dir_structure

    if scans_recursively and _is_relative_to(output_resolved, input_resolved):
        raise ConfigError(
            "Bei rekursiver Verarbeitung darf OUTPUT_DIR nicht innerhalb von "
            "INPUT_DIR liegen."
        )

    raw_overwrite, _ = _lookup(
        "OVERWRITE_EXISTING", "overwrite_existing", source, cli, file_values, False
    )
    overwrite_existing = _as_bool("OVERWRITE_EXISTING", raw_overwrite)

    raw_loop, _ = _lookup("LOOP", "loop", source, cli, file_values, False)
    loop = _as_bool("LOOP", raw_loop)

    raw_interval, _ = _lookup(
        "LOOP_INTERVAL",
        "loop_interval",
        source,
        cli,
        file_values,
        DEFAULT_LOOP_INTERVAL,
    )
    loop_interval = _as_float("LOOP_INTERVAL", raw_interval)

    raw_log_level, _ = _lookup(
        "LOG_LEVEL", "log_level", source, cli, file_values, "INFO"
    )
    log_level = _parse_log_level(str(raw_log_level))

    raw_same_dir, _ = _lookup(
        "OUTPUT_SAME_DIR", "output_same_dir", source, cli, file_values, False
    )
    output_same_dir = _as_bool("OUTPUT_SAME_DIR", raw_same_dir)

    raw_output_suffix, _ = _lookup(
        "OUTPUT_SUFFIX", "output_suffix", source, cli, file_values, False
    )
    output_suffix = _as_bool("OUTPUT_SUFFIX", raw_output_suffix)

    raw_overwrite_source, _ = _lookup(
        "OVERWRITE_SOURCE_FILE",
        "overwrite_source_file",
        source,
        cli,
        file_values,
        False,
    )
    overwrite_source_file = _as_bool(
        "OVERWRITE_SOURCE_FILE", raw_overwrite_source
    )

    raw_suffix, _ = _lookup(
        "RENAME_SUFFIX",
        "rename_suffix",
        source,
        cli,
        file_values,
        "[TAGS_REMAPPED]",
        allow_empty=True,
    )
    rename_suffix = str(raw_suffix).strip()
    if any(char in rename_suffix for char in '<>:"/\\|?*'):
        raise ConfigError(
            f"RENAME_SUFFIX enthält ungültige Zeichen für einen Dateinamen: {rename_suffix!r}"
        )
    if output_same_dir and not rename_suffix and not overwrite_source_file:
        raise ConfigError(
            "RENAME_SUFFIX darf bei OUTPUT_SAME_DIR=true nur dann leer sein, "
            "wenn OVERWRITE_SOURCE_FILE=true ist."
        )

    raw_skip_suffix, _ = _lookup(
        "SKIP_SUFFIX", "skip_suffix", source, cli, file_values, True
    )
    skip_suffix = _as_bool("SKIP_SUFFIX", raw_skip_suffix)

    raw_backup, _ = _lookup("BACKUP", "backup", source, cli, file_values, False)
    backup = _as_bool("BACKUP", raw_backup)
    raw_backup_dir, backup_dir_provided = _lookup(
        "BACKUP_DIR", "backup_dir", source, cli, file_values, None
    )
    backup_dir = _as_path("BACKUP_DIR", raw_backup_dir) if backup_dir_provided else None

    raw_retention, _ = _lookup(
        "BACKUP_RETENTION_DAYS",
        "backup_retention_days",
        source,
        cli,
        file_values,
        30,
    )
    try:
        backup_retention_days = int(str(raw_retention).strip())
    except ValueError as exc:
        raise ConfigError(
            f"BACKUP_RETENTION_DAYS muss eine ganze Zahl sein, erhalten: {raw_retention!r}"
        ) from exc
    if backup_retention_days < 0:
        raise ConfigError("BACKUP_RETENTION_DAYS darf nicht negativ sein.")

    if backup:
        if backup_dir is None:
            raise ConfigError("BACKUP_DIR ist nicht gesetzt, obwohl BACKUP=true ist.")
        if backup_dir.exists() and not backup_dir.is_dir():
            raise ConfigError(f"BACKUP_DIR ist kein Verzeichnis: {backup_dir}")
        backup_resolved = backup_dir.resolve()
        if backup_resolved == input_resolved:
            raise ConfigError("BACKUP_DIR und INPUT_DIR dürfen nicht identisch sein.")
        if backup_resolved == output_resolved:
            raise ConfigError("BACKUP_DIR und OUTPUT_DIR dürfen nicht identisch sein.")
        if scans_recursively and _is_relative_to(backup_resolved, input_resolved):
            raise ConfigError(
                "Bei rekursiver Verarbeitung darf BACKUP_DIR nicht innerhalb von "
                "INPUT_DIR liegen."
            )

    raw_rules, rules_provided = _lookup(
        "TAG_RULES", "tag_rules", source, cli, file_values, None
    )
    raw_map, map_provided = _lookup(
        "TAG_MAP", "tag_map", source, cli, file_values, None
    )

    if not rules_provided and not map_provided:
        tag_mappings = DEFAULT_TAG_MAPPINGS
        used_default_mappings = True
        tag_rules: tuple[TagRule, ...] = ()
    else:
        tag_mappings = _parse_mappings(raw_map) if map_provided else ()
        tag_rules = _parse_rules(raw_rules) if rules_provided else ()
        used_default_mappings = False

    return Config(
        input_dir=input_dir,
        output_dir=output_dir,
        filename_filter=filename_filter,
        tag_rules=tag_rules,
        tag_mappings=tag_mappings,
        recursive=recursive,
        overwrite_existing=overwrite_existing,
        log_level=log_level,
        loop=loop,
        loop_interval=loop_interval,
        single_file=single_file,
        used_default_mappings=used_default_mappings,
        output_same_dir=output_same_dir,
        rename_suffix=rename_suffix,
        skip_suffix=skip_suffix,
        backup=backup,
        backup_dir=backup_dir,
        backup_retention_days=backup_retention_days,
        replicate_source_dir_structure=replicate_source_dir_structure,
        output_suffix=output_suffix,
        overwrite_source_file=overwrite_source_file,
    )


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True
