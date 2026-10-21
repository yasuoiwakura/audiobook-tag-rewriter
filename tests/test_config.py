from __future__ import annotations

import json
from pathlib import Path

import pytest

from m4b_tag_fixer.config import (
    DEFAULT_TAG_MAPPINGS,
    ConfigError,
    TagMapping,
    load_config,
    load_file_config,
)


def _env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    env = {
        "INPUT_DIR": str(input_dir),
        "OUTPUT_DIR": str(tmp_path / "output"),
        "TAG_RULES": json.dumps(
            [
                {"tag": "album", "old": "Old Album", "new": "New Album"},
                {"tag": "artist", "old": "Old Author", "new": "New Author"},
            ]
        ),
    }
    env.update(overrides)
    return env


def test_valid_config_and_rule_order(tmp_path: Path) -> None:
    config = load_config(_env(tmp_path))

    assert config.input_dir == tmp_path / "input"
    assert config.output_dir == tmp_path / "output"
    assert config.filename_filter == "*.m4b"
    assert config.recursive is False
    assert config.replicate_source_dir_structure is False
    assert config.scans_recursively is False
    assert config.overwrite_existing is False
    assert config.loop is False
    assert config.loop_interval == 60.0
    assert config.single_file is None
    assert config.output_same_dir is False
    assert config.rename_suffix == "[TAGS_REMAPPED]"
    assert config.output_suffix is False
    assert config.overwrite_source_file is False
    assert config.skip_suffix is True
    assert config.backup is False
    assert config.backup_dir is None
    assert config.backup_retention_days == 30
    assert config.used_default_mappings is False
    assert config.tag_mappings == ()
    assert [rule.tag for rule in config.tag_rules] == ["album", "artist"]
    assert config.tag_rules[0].old == "Old Album"
    assert config.tag_rules[0].new == "New Album"


def test_default_mapping_when_no_rules_or_map_configured(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("TAG_RULES")

    config = load_config(env)

    assert config.used_default_mappings is True
    assert config.tag_rules == ()
    assert config.tag_mappings == DEFAULT_TAG_MAPPINGS


def test_explicit_empty_map_disables_default_mapping(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("TAG_RULES")
    env["TAG_MAP"] = "[]"

    config = load_config(env)

    assert config.used_default_mappings is False
    assert config.tag_mappings == ()
    assert config.tag_rules == ()


def test_explicit_empty_rules_disable_default_mapping(tmp_path: Path) -> None:
    config = load_config(_env(tmp_path, TAG_RULES="[]"))

    assert config.used_default_mappings is False
    assert config.tag_mappings == ()
    assert config.tag_rules == ()


def test_tag_rules_only_do_not_enable_default_mapping(tmp_path: Path) -> None:
    config = load_config(_env(tmp_path))

    assert config.used_default_mappings is False
    assert config.tag_mappings == ()


def test_tag_map_is_parsed_and_aliases_are_normalized(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("TAG_RULES")
    env["TAG_MAP"] = json.dumps(
        [
            {"from": "mvnm", "to": "series"},
            {"source": "mvin", "target": "series-part"},
        ]
    )

    config = load_config(env)

    assert config.tag_mappings == (
        TagMapping("series", "series"),
        TagMapping("series-part", "series-part"),
    )


def test_tag_names_are_normalized_case_insensitively(tmp_path: Path) -> None:
    env = _env(
        tmp_path,
        TAG_RULES=json.dumps([{"tag": "ALBUM", "old": "a", "new": "b"}]),
    )
    assert load_config(env).tag_rules[0].tag == "album"


def test_missing_input_dir_uses_default_and_fails_if_absent(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("INPUT_DIR")
    env["OUTPUT_DIR"] = str(tmp_path / "output")

    if Path("/in").is_dir():
        pytest.skip("/in existiert auf diesem System.")
    with pytest.raises(ConfigError, match="INPUT_DIR"):
        load_config(env)


def test_output_dir_defaults_to_out(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("OUTPUT_DIR")

    config = load_config(env)

    assert config.output_dir == Path("/out")


def test_nonexistent_input_dir(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="existiert nicht"):
        load_config(_env(tmp_path, INPUT_DIR=str(tmp_path / "missing")))


def test_input_and_output_must_differ(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    with pytest.raises(ConfigError, match="identisch"):
        load_config(_env(tmp_path, OUTPUT_DIR=str(input_dir)))


def test_recursive_rejects_output_inside_input(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="innerhalb"):
        load_config(
            _env(
                tmp_path,
                RECURSIVE="true",
                OUTPUT_DIR=str(tmp_path / "input" / "out"),
            )
        )


def test_replicate_source_dir_structure_enables_recursive_scan(
    tmp_path: Path,
) -> None:
    config = load_config(_env(tmp_path, REPLICATE_SOURCE_DIR_STRUCTURE="true"))

    assert config.replicate_source_dir_structure is True
    assert config.recursive is False
    assert config.scans_recursively is True


def test_replicate_source_dir_structure_rejects_output_inside_input(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError, match="innerhalb"):
        load_config(
            _env(
                tmp_path,
                REPLICATE_SOURCE_DIR_STRUCTURE="true",
                OUTPUT_DIR=str(tmp_path / "input" / "out"),
            )
        )


def test_replicate_source_dir_structure_rejects_invalid_boolean(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError, match="boolescher"):
        load_config(
            _env(tmp_path, REPLICATE_SOURCE_DIR_STRUCTURE="vielleicht")
        )


def test_replicate_source_dir_structure_cli_overrides_env(
    tmp_path: Path,
) -> None:
    config = load_config(
        _env(tmp_path, REPLICATE_SOURCE_DIR_STRUCTURE="true"),
        overrides={"REPLICATE_SOURCE_DIR_STRUCTURE": False},
    )

    assert config.replicate_source_dir_structure is False
    assert config.scans_recursively is False


def test_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="kein gültiges JSON"):
        load_config(_env(tmp_path, TAG_RULES="[not json"))


def test_rules_must_be_list(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="JSON-Liste"):
        load_config(_env(tmp_path, TAG_RULES='{"tag":"album","old":"a","new":"b"}'))


def test_rule_missing_required_field(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="new"):
        load_config(
            _env(
                tmp_path,
                TAG_RULES=json.dumps([{"tag": "album", "old": "a"}]),
            )
        )


def test_rule_with_non_string_value(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="String"):
        load_config(
            _env(
                tmp_path,
                TAG_RULES=json.dumps([{"tag": "album", "old": 1, "new": "b"}]),
            )
        )


def test_unknown_tag_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="unbekanntes Tag"):
        load_config(
            _env(
                tmp_path,
                TAG_RULES=json.dumps([{"tag": "not_a_tag", "old": "a", "new": "b"}]),
            )
        )


def test_track_rule_requires_numbers(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Zahl"):
        load_config(
            _env(
                tmp_path,
                TAG_RULES=json.dumps([{"tag": "track", "old": "3", "new": "four"}]),
            )
        )


def test_identical_old_and_new_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="identisch"):
        load_config(
            _env(
                tmp_path,
                TAG_RULES=json.dumps([{"tag": "album", "old": "a", "new": "a"}]),
            )
        )


def test_invalid_boolean(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="boolescher"):
        load_config(_env(tmp_path, RECURSIVE="vielleicht"))


def test_invalid_log_level(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        load_config(_env(tmp_path, LOG_LEVEL="CHATTY"))


def test_filename_filter_flags_loop_and_single_file(tmp_path: Path, make_m4b) -> None:
    source = make_m4b("book.m4b")
    config = load_config(
        _env(
            tmp_path,
            FILENAME_FILTER="Book_*.m4b",
            RECURSIVE="yes",
            OVERWRITE_EXISTING="1",
            LOG_LEVEL="debug",
            LOOP="true",
            LOOP_INTERVAL="5",
            SINGLE_FILE=str(source),
            INPUT_DIR=str(tmp_path / "nicht-vorhanden"),
            OUTPUT_SAME_DIR="true",
            RENAME_SUFFIX="[TEST]",
            SKIP_SUFFIX="false",
        )
    )
    assert config.filename_filter == "Book_*.m4b"
    assert config.recursive is True
    assert config.overwrite_existing is True
    assert config.log_level == "DEBUG"
    assert config.loop is True
    assert config.loop_interval == 5.0
    assert config.single_file == source
    assert config.output_same_dir is True
    assert config.rename_suffix == "[TEST]"
    assert config.skip_suffix is False


def test_single_file_must_be_m4b(tmp_path: Path) -> None:
    other = tmp_path / "book.mp3"
    other.write_bytes(b"x")
    with pytest.raises(ConfigError, match="\\.m4b"):
        load_config(_env(tmp_path, INPUT_DIR=str(tmp_path), SINGLE_FILE=str(other)))


def test_invalid_tag_map(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("TAG_RULES")
    env["TAG_MAP"] = json.dumps([{"from": "album"}])
    with pytest.raises(ConfigError, match="'from' und 'to'"):
        load_config(env)


def test_tag_map_unknown_tag(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.pop("TAG_RULES")
    env["TAG_MAP"] = json.dumps([{"from": "album", "to": "nope"}])
    with pytest.raises(ConfigError, match="unbekanntes Tag"):
        load_config(env)


def test_yaml_file_config(tmp_path: Path, make_m4b) -> None:
    make_m4b("book.m4b")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                f"input_dir: {tmp_path / 'input'}",
                f"output_dir: {tmp_path / 'output'}",
                "filename_filter: '*.m4b'",
                "log_level: DEBUG",
                "loop: false",
                "replicate_source_dir_structure: true",
                "tag_map:",
                "  - from: album",
                "    to: series",
            ]
        ),
        encoding="utf-8",
    )

    file_config = load_file_config(config_path)
    config = load_config(env={}, file_config=file_config)

    assert config.filename_filter == "*.m4b"
    assert config.log_level == "DEBUG"
    assert config.replicate_source_dir_structure is True
    assert config.tag_mappings == (TagMapping("album", "series"),)
    assert config.used_default_mappings is False


def test_yaml_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("unknown_key: value\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unbekannter YAML"):
        load_file_config(path)


def test_precedence_yaml_then_env_then_cli(tmp_path: Path, make_m4b) -> None:
    make_m4b("book.m4b")
    file_config = {
        "input_dir": str(tmp_path / "input"),
        "output_dir": str(tmp_path / "yaml-out"),
        "tag_map": [{"from": "album", "to": "series"}],
    }
    env = {
        "OUTPUT_DIR": str(tmp_path / "env-out"),
        "TAG_MAP": json.dumps([{"from": "track", "to": "series-part"}]),
    }
    cli = {
        "OUTPUT_DIR": str(tmp_path / "cli-out"),
        "TAG_MAP": json.dumps([{"from": "title", "to": "album"}]),
    }

    config = load_config(env=env, overrides=cli, file_config=file_config)

    assert config.output_dir == tmp_path / "cli-out"
    assert config.tag_mappings == (TagMapping("title", "album"),)


def test_empty_env_values_use_default_mapping(tmp_path: Path) -> None:
    config = load_config(_env(tmp_path, TAG_RULES="", TAG_MAP=""))

    assert config.used_default_mappings is True
    assert config.tag_mappings == DEFAULT_TAG_MAPPINGS


def test_empty_env_values_do_not_override_yaml_map(tmp_path: Path, make_m4b) -> None:
    make_m4b("book.m4b")
    file_config = {
        "input_dir": str(tmp_path / "input"),
        "output_dir": str(tmp_path / "output"),
        "tag_map": [{"from": "album", "to": "series"}],
    }
    env = {"TAG_MAP": "", "TAG_RULES": ""}

    config = load_config(env=env, file_config=file_config)

    assert config.used_default_mappings is False
    assert config.tag_mappings == (TagMapping("album", "series"),)


def test_shipped_config_example_is_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "config.example.yml"
    data = load_file_config(path)

    assert data["tag_map"] == [
        {"from": "album", "to": "series"},
        {"from": "track", "to": "series-part"},
        {"from": "title", "to": "album"},
    ]


def test_same_dir_requires_non_empty_suffix(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="RENAME_SUFFIX"):
        load_config(_env(tmp_path, OUTPUT_SAME_DIR="true", RENAME_SUFFIX=""))


def test_same_dir_allows_empty_suffix_when_overwriting_source(
    tmp_path: Path,
) -> None:
    config = load_config(
        _env(
            tmp_path,
            OUTPUT_SAME_DIR="true",
            RENAME_SUFFIX="",
            OVERWRITE_SOURCE_FILE="true",
            BACKUP="true",
            BACKUP_DIR=str(tmp_path / "backup"),
        )
    )

    assert config.rename_suffix == ""
    assert config.overwrite_source_file is True


def test_output_suffix_is_parsed(tmp_path: Path) -> None:
    config = load_config(_env(tmp_path, OUTPUT_SUFFIX="true"))

    assert config.output_suffix is True


def test_overwrite_source_file_allows_missing_backup(tmp_path: Path) -> None:
    config = load_config(_env(tmp_path, OVERWRITE_SOURCE_FILE="true"))

    assert config.overwrite_source_file is True
    assert config.backup is False


def test_overwrite_source_file_is_parsed_with_backup(tmp_path: Path) -> None:
    config = load_config(
        _env(
            tmp_path,
            OVERWRITE_SOURCE_FILE="true",
            BACKUP="true",
            BACKUP_DIR=str(tmp_path / "backup"),
        )
    )

    assert config.overwrite_source_file is True
    assert config.output_suffix is False


def test_rename_suffix_rejects_path_separators(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="ungültige Zeichen"):
        load_config(_env(tmp_path, OUTPUT_SAME_DIR="true", RENAME_SUFFIX="a/b"))


def test_backup_requires_backup_dir(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="BACKUP_DIR"):
        load_config(_env(tmp_path, BACKUP="true"))


def test_backup_dir_is_parsed(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    config = load_config(
        _env(
            tmp_path,
            BACKUP="true",
            BACKUP_DIR=str(backup_dir),
        )
    )

    assert config.backup is True
    assert config.backup_dir == backup_dir


def test_backup_dir_must_differ_from_output(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="BACKUP_DIR und OUTPUT_DIR"):
        load_config(
            _env(
                tmp_path,
                BACKUP="true",
                BACKUP_DIR=str(tmp_path / "output"),
            )
        )


def test_recursive_backup_inside_input_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="BACKUP_DIR"):
        load_config(
            _env(
                tmp_path,
                RECURSIVE="true",
                BACKUP="true",
                BACKUP_DIR=str(tmp_path / "input" / "backup"),
            )
        )


def test_backup_dir_must_differ_from_input(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="BACKUP_DIR und INPUT_DIR"):
        load_config(
            _env(
                tmp_path,
                BACKUP="true",
                BACKUP_DIR=str(tmp_path / "input"),
            )
        )


def test_backup_retention_days(tmp_path: Path) -> None:
    config = load_config(
        _env(tmp_path, BACKUP="true", BACKUP_DIR=str(tmp_path / "backup"), BACKUP_RETENTION_DAYS="7")
    )
    assert config.backup_retention_days == 7

    disabled = load_config(_env(tmp_path, BACKUP_RETENTION_DAYS="0"))
    assert disabled.backup_retention_days == 0


def test_backup_retention_days_must_be_non_negative(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="negativ"):
        load_config(_env(tmp_path, BACKUP_RETENTION_DAYS="-1"))


def test_backup_retention_days_must_be_integer(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="ganze Zahl"):
        load_config(_env(tmp_path, BACKUP_RETENTION_DAYS="viele"))
