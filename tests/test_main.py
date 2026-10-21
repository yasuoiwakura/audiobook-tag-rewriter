from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import pytest

from m4b_tag_fixer.config import Config, load_config
from m4b_tag_fixer.main import _run_loop, main
from m4b_tag_fixer.metadata import read_tags


def _set_valid_env(monkeypatch, tmp_path: Path) -> Path:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("FILENAME_FILTER", "*.m4b")
    monkeypatch.setenv(
        "TAG_RULES",
        json.dumps([{"tag": "album", "old": "Old Album", "new": "New Album"}]),
    )
    for name in (
        "TAG_MAP",
        "SINGLE_FILE",
        "CONFIG_FILE",
        "ENV_FILE",
        "LOOP",
        "REPLICATE_SOURCE_DIR_STRUCTURE",
        "OUTPUT_SUFFIX",
        "OVERWRITE_SOURCE_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    return input_dir


def _isolate_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_main_success_returns_zero(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})

    assert main([]) == 0
    assert (tmp_path / "output" / "book.m4b").exists()


def test_main_config_error_returns_two(monkeypatch, tmp_path: Path) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TAG_RULES", "{broken")

    assert main([]) == 2


def test_main_processing_error_returns_one(monkeypatch, tmp_path: Path) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    input_dir = _set_valid_env(monkeypatch, tmp_path)
    (input_dir / "broken.m4b").write_bytes(b"not an mp4")

    assert main([]) == 1


def test_main_without_matching_files_returns_zero(
    monkeypatch, tmp_path: Path
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)

    assert main([]) == 0


def test_main_single_file_argument(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    source = make_m4b("single.m4b", {"\xa9alb": ["Old Album"]})
    monkeypatch.delenv("INPUT_DIR")

    assert main([str(source), "--no-loop"]) == 0
    assert read_tags(tmp_path / "output" / "single.m4b").get("album") == [
        "New Album"
    ]


def test_cli_overrides_env(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    source = make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    other_output = tmp_path / "cli-output"

    assert main(["--output-dir", str(other_output), "--no-loop"]) == 0
    assert (other_output / "book.m4b").exists()
    assert source.exists()


def test_env_file_is_loaded(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    for name in (
        "INPUT_DIR",
        "OUTPUT_DIR",
        "TAG_RULES",
        "TAG_MAP",
        "SINGLE_FILE",
        "CONFIG_FILE",
        "ENV_FILE",
        "LOOP",
        "REPLICATE_SOURCE_DIR_STRUCTURE",
        "OUTPUT_SUFFIX",
        "OVERWRITE_SOURCE_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f"INPUT_DIR={input_dir}",
                f"OUTPUT_DIR={tmp_path / 'env-output'}",
                'TAG_RULES=[{"tag":"album","old":"Old Album","new":"From Dotenv"}]',
            ]
        ),
        encoding="utf-8",
    )

    assert main(["--no-loop"]) == 0
    assert read_tags(tmp_path / "env-output" / "book.m4b").get("album") == [
        "From Dotenv"
    ]


def test_yaml_config_via_cli(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    for name in (
        "INPUT_DIR",
        "OUTPUT_DIR",
        "TAG_RULES",
        "TAG_MAP",
        "SINGLE_FILE",
        "CONFIG_FILE",
        "ENV_FILE",
        "LOOP",
        "REPLICATE_SOURCE_DIR_STRUCTURE",
        "OUTPUT_SUFFIX",
        "OVERWRITE_SOURCE_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                f"input_dir: {input_dir}",
                f"output_dir: {tmp_path / 'yaml-output'}",
                "tag_map:",
                "  - from: album",
                "    to: series",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["--config", str(config_path), "--no-loop"]) == 0
    result = read_tags(tmp_path / "yaml-output" / "book.m4b")
    assert result.get("series") == ["Old Album"]
    assert result.get("album") == ["Old Album"]


def test_loop_runs_once_and_stops(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    config = load_config()
    assert isinstance(config, Config)
    config = Config(
        input_dir=config.input_dir,
        output_dir=config.output_dir,
        filename_filter=config.filename_filter,
        tag_rules=config.tag_rules,
        loop=True,
        loop_interval=0.01,
    )
    stop = threading.Event()
    timer = threading.Timer(0.05, stop.set)
    timer.start()
    try:
        assert _run_loop(config, stop) == 0
    finally:
        timer.cancel()

    assert (tmp_path / "output" / "book.m4b").exists()


def test_main_replicate_source_dir_structure_from_env(
    monkeypatch, tmp_path: Path, make_m4b
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    make_m4b("German/book.m4b", {"\xa9alb": ["Old Album"]})
    monkeypatch.setenv("REPLICATE_SOURCE_DIR_STRUCTURE", "true")

    assert main(["--no-loop"]) == 0
    output = tmp_path / "output" / "German" / "book.m4b"
    assert output.exists()
    assert read_tags(output).get("album") == ["New Album"]


def test_main_no_replicate_overrides_env(
    monkeypatch, tmp_path: Path, make_m4b
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    make_m4b("German/book.m4b", {"\xa9alb": ["Old Album"]})
    monkeypatch.setenv("REPLICATE_SOURCE_DIR_STRUCTURE", "true")

    assert main(["--no-replicate-source-dir-structure", "--no-loop"]) == 0
    assert not (tmp_path / "output" / "German").exists()


def test_main_output_suffix_from_env(
    monkeypatch, tmp_path: Path, make_m4b
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    make_m4b("German/book.m4b", {"\xa9alb": ["Old Album"]})
    monkeypatch.setenv("REPLICATE_SOURCE_DIR_STRUCTURE", "true")
    monkeypatch.setenv("OUTPUT_SUFFIX", "true")

    assert main(["--no-loop"]) == 0
    assert (
        tmp_path / "output" / "German" / "book [TAGS_REMAPPED].m4b"
    ).exists()


def test_main_warns_when_overwriting_without_backup(
    monkeypatch,
    tmp_path: Path,
    make_m4b,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    source = make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    monkeypatch.setenv("OUTPUT_SAME_DIR", "true")
    monkeypatch.setenv("OVERWRITE_SOURCE_FILE", "true")
    monkeypatch.setenv("BACKUP", "false")
    caplog.set_level(logging.INFO)

    assert main(["--no-loop"]) == 0
    assert read_tags(source).get("album") == ["New Album"]
    assert (
        "WARNUNG: OVERWRITE_SOURCE_FILE=true ohne BACKUP=true" in caplog.text
    )


def test_main_same_dir_copy_with_suffix(
    monkeypatch, tmp_path: Path, make_m4b
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    source = make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    before = source.read_bytes()

    assert main(["--same-dir", "--no-loop"]) == 0

    target = source.parent / f"{source.stem} [TAGS_REMAPPED].m4b"
    assert target.exists()
    assert source.read_bytes() == before
    assert read_tags(target).get("album") == ["New Album"]


def test_main_backup_from_env(monkeypatch, tmp_path: Path, make_m4b) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    source = make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    backup_dir = tmp_path / "backup"
    monkeypatch.setenv("BACKUP", "true")
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    before = source.read_bytes()

    assert main(["--no-loop"]) == 0
    assert (backup_dir / "book.m4b").read_bytes() == before
    assert source.read_bytes() == before


def test_idle_loop_does_not_log_summary_at_info(
    monkeypatch, tmp_path: Path, caplog
) -> None:
    _isolate_cwd(monkeypatch, tmp_path)
    _set_valid_env(monkeypatch, tmp_path)
    config = load_config()
    config = Config(
        input_dir=config.input_dir,
        output_dir=config.output_dir,
        filename_filter=config.filename_filter,
        tag_rules=config.tag_rules,
        loop=True,
        loop_interval=0.01,
    )
    stop = threading.Event()
    timer = threading.Timer(0.05, stop.set)
    caplog.set_level(logging.INFO)
    timer.start()
    try:
        assert _run_loop(config, stop) == 0
    finally:
        timer.cancel()

    assert "Zusammenfassung" not in caplog.text
    assert "Nächster Durchlauf" not in caplog.text
