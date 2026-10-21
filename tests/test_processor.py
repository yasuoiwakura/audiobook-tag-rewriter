from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

import pytest

from m4b_tag_fixer.config import DEFAULT_TAG_MAPPINGS, Config, TagMapping, TagRule
from m4b_tag_fixer.metadata import read_tags
from m4b_tag_fixer.processor import BatchProcessor


def _config(
    tmp_path: Path,
    rules: tuple[TagRule, ...] = (),
    *,
    mappings: tuple[TagMapping, ...] = (),
    filename_filter: str = "*.m4b",
    recursive: bool = False,
    overwrite_existing: bool = False,
    single_file: Path | None = None,
    output_same_dir: bool = False,
    rename_suffix: str = "[TAGS_REMAPPED]",
    skip_suffix: bool = True,
    backup: bool = False,
    backup_dir: Path | None = None,
    backup_retention_days: int = 30,
    replicate_source_dir_structure: bool = False,
    output_suffix: bool = False,
    overwrite_source_file: bool = False,
) -> Config:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    return Config(
        input_dir=input_dir,
        output_dir=tmp_path / "output",
        filename_filter=filename_filter,
        tag_rules=rules,
        tag_mappings=mappings,
        recursive=recursive,
        overwrite_existing=overwrite_existing,
        single_file=single_file,
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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_filename_filter_and_extension(tmp_path: Path, make_m4b) -> None:
    config = _config(tmp_path, filename_filter="Book_*.m4b")
    input_dir = config.input_dir

    make_m4b("Book_One.m4b")
    make_m4b("book_two.M4B")
    make_m4b("Other.m4b")
    (input_dir / "Book_notes.txt").write_text("x", encoding="utf-8")

    files = BatchProcessor(config).discover_files()

    assert [path.name for path in files] == ["Book_One.m4b", "book_two.M4B"]


def test_non_recursive_ignores_subdirectories(tmp_path: Path, make_m4b) -> None:
    config = _config(tmp_path)
    make_m4b("top.m4b")
    make_m4b("sub/nested.m4b")

    files = BatchProcessor(config).discover_files()

    assert [path.name for path in files] == ["top.m4b"]


def test_recursive_processing_preserves_relative_structure(
    tmp_path: Path, make_m4b
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        recursive=True,
    )
    make_m4b("top.m4b", {"\xa9alb": ["Old Album"]})
    make_m4b("sub/nested.m4b", {"\xa9alb": ["Old Album"]})

    summary = BatchProcessor(config).run()

    assert summary.found == 2
    assert summary.processed == 2
    assert (config.output_dir / "top.m4b").exists()
    assert (config.output_dir / "sub" / "nested.m4b").exists()
    assert read_tags(config.output_dir / "sub" / "nested.m4b").get("album") == [
        "New Album"
    ]


def test_replicate_source_dir_structure_mirrors_without_suffix(
    tmp_path: Path, make_m4b
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        replicate_source_dir_structure=True,
    )
    make_m4b("top.m4b", {"\xa9alb": ["Old Album"]})
    make_m4b("German/nested.m4b", {"\xa9alb": ["Old Album"]})
    make_m4b("German/Sub/deep.m4b", {"\xa9alb": ["Old Album"]})

    summary = BatchProcessor(config).run()

    assert summary.found == 3
    assert summary.processed == 3
    assert (config.output_dir / "top.m4b").exists()
    assert (config.output_dir / "German" / "nested.m4b").exists()
    assert (config.output_dir / "German" / "Sub" / "deep.m4b").exists()
    assert read_tags(config.output_dir / "German" / "nested.m4b").get("album") == [
        "New Album"
    ]


def test_replicate_source_dir_structure_with_output_suffix(
    tmp_path: Path, make_m4b
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        replicate_source_dir_structure=True,
        output_suffix=True,
    )
    make_m4b("German/nested.m4b", {"\xa9alb": ["Old Album"]})

    BatchProcessor(config).run()

    assert (
        config.output_dir / "German" / "nested [TAGS_REMAPPED].m4b"
    ).exists()


def test_replicate_source_dir_structure_skips_existing_output(
    tmp_path: Path, make_m4b
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        replicate_source_dir_structure=True,
    )
    make_m4b("German/nested.m4b", {"\xa9alb": ["Old Album"]})
    existing = config.output_dir / "German" / "nested.m4b"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep me")

    summary = BatchProcessor(config).run()

    assert summary.skipped == 1
    assert summary.processed == 0
    assert existing.read_bytes() == b"keep me"


def test_replicate_source_dir_structure_with_empty_suffix(
    tmp_path: Path, make_m4b
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        replicate_source_dir_structure=True,
        output_suffix=True,
        rename_suffix="",
    )
    make_m4b("German/nested.m4b", {"\xa9alb": ["Old Album"]})

    BatchProcessor(config).run()

    assert (config.output_dir / "German" / "nested.m4b").exists()


def test_multiple_rules_and_source_remains_untouched(
    tmp_path: Path, sample_m4b: Path
) -> None:
    source = sample_m4b
    before = _digest(source)

    config = _config(
        tmp_path,
        (
            TagRule("album", "Old Album", "New Album"),
            TagRule("artist", "Old Author", "New Author"),
            TagRule("title", "Old Title", "New Title"),
            TagRule("track", "3", "9"),
        ),
    )

    summary = BatchProcessor(config).run()
    output = config.output_dir / "book.m4b"
    result = read_tags(output)

    assert summary.found == 1
    assert summary.processed == 1
    assert summary.failed == 0
    assert summary.changes == 4
    assert result.get("album") == ["New Album"]
    assert result.get("artist") == ["New Author"]
    assert result.get("title") == ["New Title"]
    assert result.get("track") == ["9"]
    assert result.track_total == 12
    assert _digest(source) == before


def test_sequential_rules_on_same_tag(tmp_path: Path, sample_m4b: Path) -> None:
    config = _config(
        tmp_path,
        (
            TagRule("album", "Old Album", "Intermediate"),
            TagRule("album", "Intermediate", "Final"),
        ),
    )

    summary = BatchProcessor(config).run()

    assert summary.changes == 2
    assert read_tags(config.output_dir / "book.m4b").get("album") == ["Final"]


def test_no_matching_rule_copies_unchanged_file(
    tmp_path: Path, sample_m4b: Path
) -> None:
    source = sample_m4b
    config = _config(
        tmp_path,
        (TagRule("album", "Different Album", "New Album"),),
    )

    summary = BatchProcessor(config).run()

    assert summary.processed == 1
    assert summary.changes == 0
    output = config.output_dir / "book.m4b"
    assert output.exists()
    assert output.read_bytes() == source.read_bytes()


def test_existing_output_is_skipped_by_default(tmp_path: Path, sample_m4b: Path) -> None:
    config = _config(tmp_path, (TagRule("album", "Old Album", "New Album"),))
    config.output_dir.mkdir()
    existing = config.output_dir / "book.m4b"
    existing.write_bytes(b"keep me")

    summary = BatchProcessor(config).run()

    assert summary.processed == 0
    assert summary.skipped == 1
    assert summary.changes == 0
    assert existing.read_bytes() == b"keep me"


def test_existing_output_can_be_overwritten_when_enabled(
    tmp_path: Path, sample_m4b: Path
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        overwrite_existing=True,
    )
    config.output_dir.mkdir()
    existing = config.output_dir / "book.m4b"
    existing.write_bytes(b"old output")

    summary = BatchProcessor(config).run()

    assert summary.processed == 1
    assert summary.skipped == 0
    assert read_tags(existing).get("album") == ["New Album"]


def test_corrupt_file_does_not_stop_other_files(tmp_path: Path, make_m4b) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        filename_filter="*.m4b",
    )
    make_m4b("good.m4b", {"\xa9alb": ["Old Album"]})
    (config.input_dir / "bad.m4b").write_bytes(b"not an mp4")

    summary = BatchProcessor(config).run()

    assert summary.found == 2
    assert summary.processed == 1
    assert summary.failed == 1
    assert (config.output_dir / "good.m4b").exists()
    assert not (config.output_dir / "bad.m4b").exists()


def test_failed_write_leaves_no_output_and_source_intact(
    tmp_path: Path, sample_m4b: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = sample_m4b
    before = _digest(source)
    config = _config(tmp_path, (TagRule("album", "Old Album", "New Album"),))

    def fail(*args, **kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr("m4b_tag_fixer.processor.write_changes", fail)

    summary = BatchProcessor(config).run()

    assert summary.failed == 1
    assert not (config.output_dir / "book.m4b").exists()
    assert _digest(source) == before
    assert not list(config.output_dir.glob("*.tmp"))


def test_output_directory_is_created(tmp_path: Path, make_m4b) -> None:
    config = _config(tmp_path, (TagRule("album", "Old Album", "New Album"),))
    make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})

    summary = BatchProcessor(config).run()

    assert summary.processed == 1
    assert config.output_dir.is_dir()


def test_failed_overwrite_keeps_existing_output(
    tmp_path: Path, sample_m4b: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(
        tmp_path,
        (TagRule("album", "Old Album", "New Album"),),
        overwrite_existing=True,
    )
    config.output_dir.mkdir()
    existing = config.output_dir / "book.m4b"
    existing.write_bytes(b"previous output")

    def fail(*args, **kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr("m4b_tag_fixer.processor.write_changes", fail)

    summary = BatchProcessor(config).run()

    assert summary.failed == 1
    assert existing.read_bytes() == b"previous output"


def test_colliding_output_path_gets_suffix_instead_of_overwriting_source(
    tmp_path: Path, make_m4b
) -> None:
    from dataclasses import replace

    config = _config(tmp_path, (TagRule("album", "Old Album", "New Album"),))
    source = make_m4b("book.m4b", {"\xa9alb": ["Old Album"]})
    before = _digest(source)
    colliding = replace(config, output_dir=config.input_dir)

    summary = BatchProcessor(colliding).run()
    target = source.parent / f"{source.stem} [TAGS_REMAPPED].m4b"

    assert summary.failed == 0
    assert summary.processed == 1
    assert _digest(source) == before
    assert read_tags(source).get("album") == ["Old Album"]
    assert read_tags(target).get("album") == ["New Album"]


def test_default_mapping_end_to_end(tmp_path: Path, sample_m4b: Path) -> None:
    config = _config(tmp_path, mappings=DEFAULT_TAG_MAPPINGS)

    summary = BatchProcessor(config).run()
    result = read_tags(config.output_dir / "book.m4b")

    assert summary.changes == 3
    assert result.get("album") == ["Old Title"]
    assert result.get("title") == ["Old Title"]
    assert result.get("series") == ["Old Album"]
    assert result.get("series-part") == ["3"]
    assert result.get("track") == ["3"]


def test_mapping_runs_before_value_rules(tmp_path: Path, sample_m4b: Path) -> None:
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Title", "Final Title"),),
        mappings=(
            TagMapping("album", "series"),
            TagMapping("title", "album"),
        ),
    )

    summary = BatchProcessor(config).run()
    result = read_tags(config.output_dir / "book.m4b")

    assert summary.changes == 3
    assert result.get("series") == ["Old Album"]
    assert result.get("album") == ["Final Title"]


def test_single_file_mode(tmp_path: Path, sample_m4b: Path) -> None:
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        filename_filter="*.mp3",
        single_file=sample_m4b,
    )

    files = BatchProcessor(config).discover_files()
    summary = BatchProcessor(config).run()

    assert files == [sample_m4b]
    assert summary.found == 1
    assert summary.processed == 1
    assert read_tags(config.output_dir / sample_m4b.name).get("album") == [
        "New Album"
    ]


def test_single_file_ignores_input_dir_existence(
    tmp_path: Path, sample_m4b: Path
) -> None:
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        single_file=sample_m4b,
    )
    missing = tmp_path / "does-not-exist"
    from dataclasses import replace

    config = replace(config, input_dir=missing)

    summary = BatchProcessor(config).run()

    assert summary.processed == 1


def test_single_file_in_source_dir_gets_suffix_without_overwrite(
    tmp_path: Path, sample_m4b: Path
) -> None:
    from dataclasses import replace

    before = _digest(sample_m4b)
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        single_file=sample_m4b,
    )
    config = replace(config, output_dir=sample_m4b.parent)

    summary = BatchProcessor(config).run()
    target = sample_m4b.parent / f"{sample_m4b.stem} [TAGS_REMAPPED].m4b"

    assert summary.processed == 1
    assert target.exists()
    assert _digest(sample_m4b) == before
    assert read_tags(sample_m4b).get("album") == ["Old Album"]
    assert read_tags(target).get("album") == ["New Album"]


def test_single_file_in_place_with_backup(
    tmp_path: Path, sample_m4b: Path
) -> None:
    from dataclasses import replace

    before = _digest(sample_m4b)
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        single_file=sample_m4b,
        overwrite_source_file=True,
        backup=True,
        backup_dir=backup_dir,
    )
    config = replace(config, output_dir=sample_m4b.parent)

    summary = BatchProcessor(config).run()

    assert summary.processed == 1
    assert summary.changes == 1
    assert _digest(sample_m4b) != before
    assert read_tags(sample_m4b).get("album") == ["New Album"]
    assert _digest(backup_dir / sample_m4b.name) == before


def test_same_dir_copy_with_suffix_leaves_source_untouched(
    tmp_path: Path, sample_m4b: Path
) -> None:
    before = _digest(sample_m4b)
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        output_same_dir=True,
    )

    summary = BatchProcessor(config).run()
    target = sample_m4b.parent / f"{sample_m4b.stem} [TAGS_REMAPPED].m4b"

    assert summary.processed == 1
    assert summary.changes == 1
    assert target.exists()
    assert _digest(sample_m4b) == before
    assert read_tags(sample_m4b).get("album") == ["Old Album"]
    assert read_tags(target).get("album") == ["New Album"]


def test_suffixed_input_files_are_skipped(tmp_path: Path, make_m4b) -> None:
    make_m4b("book.m4b")
    suffixed = make_m4b("book [TAGS_REMAPPED].m4b")
    config = _config(tmp_path)

    files = BatchProcessor(config).discover_files()

    assert suffixed not in files
    assert [path.name for path in files] == ["book.m4b"]


def test_same_dir_copy_collision_is_skipped(tmp_path: Path, sample_m4b: Path) -> None:
    before = _digest(sample_m4b)
    target = sample_m4b.parent / f"{sample_m4b.stem} [TAGS_REMAPPED].m4b"
    target.write_bytes(b"existing")
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        output_same_dir=True,
    )

    summary = BatchProcessor(config).run()

    assert summary.skipped == 1
    assert summary.processed == 0
    assert _digest(sample_m4b) == before
    assert target.read_bytes() == b"existing"


def test_same_dir_copy_supports_custom_suffix(
    tmp_path: Path, sample_m4b: Path
) -> None:
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        output_same_dir=True,
        rename_suffix="[TEST]",
    )

    BatchProcessor(config).run()

    assert (sample_m4b.parent / f"{sample_m4b.stem} [TEST].m4b").exists()


def test_same_dir_overwrites_source_in_place_with_backup(
    tmp_path: Path, sample_m4b: Path
) -> None:
    before = _digest(sample_m4b)
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        output_same_dir=True,
        overwrite_source_file=True,
        backup=True,
        backup_dir=backup_dir,
    )

    summary = BatchProcessor(config).run()

    assert summary.processed == 1
    assert summary.changes == 1
    assert summary.backups == 1
    assert _digest(sample_m4b) != before
    assert read_tags(sample_m4b).get("album") == ["New Album"]
    assert not (
        sample_m4b.parent / f"{sample_m4b.stem} [TAGS_REMAPPED].m4b"
    ).exists()
    assert _digest(backup_dir / sample_m4b.name) == before


def test_output_suffix_wins_over_overwrite_source_file(
    tmp_path: Path, sample_m4b: Path
) -> None:
    before = _digest(sample_m4b)
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        output_same_dir=True,
        overwrite_source_file=True,
        output_suffix=True,
        backup=True,
        backup_dir=tmp_path / "backup",
    )

    summary = BatchProcessor(config).run()
    target = sample_m4b.parent / f"{sample_m4b.stem} [TAGS_REMAPPED].m4b"

    assert summary.processed == 1
    assert target.exists()
    assert _digest(sample_m4b) == before
    assert read_tags(sample_m4b).get("album") == ["Old Album"]
    assert read_tags(target).get("album") == ["New Album"]


def test_overwrite_source_file_without_backup_warns_but_succeeds(
    tmp_path: Path, sample_m4b: Path, caplog: pytest.LogCaptureFixture
) -> None:
    before = _digest(sample_m4b)
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        output_same_dir=True,
        overwrite_source_file=True,
        backup=False,
    )
    caplog.set_level(logging.INFO)

    summary = BatchProcessor(config).run()

    assert summary.failed == 0
    assert summary.processed == 1
    assert summary.backups == 0
    assert _digest(sample_m4b) != before
    assert read_tags(sample_m4b).get("album") == ["New Album"]
    assert "OHNE Backup" in caplog.text
    assert not (tmp_path / "backup").exists()


def test_backup_before_processing_keeps_source_and_copies_it(
    tmp_path: Path, sample_m4b: Path
) -> None:
    before = _digest(sample_m4b)
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=backup_dir,
    )

    summary = BatchProcessor(config).run()
    backup = backup_dir / sample_m4b.name

    assert summary.backups == 1
    assert summary.processed == 1
    assert backup.exists()
    assert _digest(backup) == before
    assert _digest(sample_m4b) == before
    assert read_tags(backup).get("album") == ["Old Album"]


def test_backup_preserves_relative_paths(tmp_path: Path, make_m4b) -> None:
    source = make_m4b("sub/book.m4b", {"\xa9alb": ["Old Album"]})
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        recursive=True,
        backup=True,
        backup_dir=backup_dir,
    )

    summary = BatchProcessor(config).run()

    assert summary.backups == 1
    assert (backup_dir / "sub" / source.name).exists()


def test_unchanged_backup_is_not_copied_again(
    tmp_path: Path, sample_m4b: Path
) -> None:
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=backup_dir,
        overwrite_existing=True,
    )
    BatchProcessor(config).run()
    first_backup = backup_dir / sample_m4b.name
    first_stat = first_backup.stat()

    summary = BatchProcessor(config).run()
    second_stat = first_backup.stat()

    assert summary.backups == 0
    assert first_stat.st_mtime_ns == second_stat.st_mtime_ns


def test_backup_is_updated_when_source_changes(
    tmp_path: Path, sample_m4b: Path
) -> None:
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=backup_dir,
        overwrite_existing=True,
    )
    BatchProcessor(config).run()
    backup = backup_dir / sample_m4b.name
    old_backup = backup.read_bytes()

    sample_m4b.write_bytes(sample_m4b.read_bytes() + b"changed")
    summary = BatchProcessor(config).run()

    assert summary.backups == 1
    assert backup.read_bytes() != old_backup


def test_backup_failure_prevents_processing(
    tmp_path: Path, sample_m4b: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _digest(sample_m4b)
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=tmp_path / "backup",
    )

    def fail(*args, **kwargs):
        raise OSError("simulated backup failure")

    monkeypatch.setattr("m4b_tag_fixer.processor.shutil.copy2", fail)

    summary = BatchProcessor(config).run()

    assert summary.failed == 1
    assert summary.processed == 0
    assert not (config.output_dir / sample_m4b.name).exists()
    assert _digest(sample_m4b) == before


def test_change_table_and_timings_are_logged(
    tmp_path: Path, sample_m4b: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
    )
    caplog.set_level(logging.INFO)

    BatchProcessor(config).run()

    messages = [record.getMessage() for record in caplog.records]
    assert any("Tag" in message and "Old Value" in message and "New Value" in message for message in messages)
    album_row = next(message for message in messages if message.strip().startswith("album "))
    assert sample_m4b.name not in album_row
    assert "Old Album" in album_row
    assert "New Album" in album_row
    assert any("Zeiten: Backup" in message for message in messages)
    assert any("Tags" in message and "Gesamt" in message for message in messages)


def test_empty_loop_is_debug_not_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = _config(tmp_path)
    config = type(config)(
        input_dir=config.input_dir,
        output_dir=config.output_dir,
        filename_filter=config.filename_filter,
        tag_rules=config.tag_rules,
        loop=True,
    )
    caplog.set_level(logging.INFO)

    BatchProcessor(config).run()

    assert "Keine passenden .m4b-Dateien" not in caplog.text
    assert "Gefundene .m4b-Dateien" not in caplog.text


def test_empty_one_shot_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = _config(tmp_path)
    caplog.set_level(logging.INFO)

    BatchProcessor(config).run()

    assert "Keine passenden .m4b-Dateien" in caplog.text


def test_loop_skipped_output_is_quiet(
    tmp_path: Path, sample_m4b: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = _config(tmp_path)
    config = type(config)(
        input_dir=config.input_dir,
        output_dir=config.output_dir,
        filename_filter=config.filename_filter,
        tag_rules=config.tag_rules,
        loop=True,
    )
    config.output_dir.mkdir()
    (config.output_dir / sample_m4b.name).write_bytes(b"existing")
    caplog.set_level(logging.INFO)

    BatchProcessor(config).run()

    assert "existiert bereits" not in caplog.text
    assert "Datei:" not in caplog.text


def test_old_backups_are_cleaned_after_new_backup(
    tmp_path: Path, sample_m4b: Path
) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    old_backup = backup_dir / "old.m4b"
    old_backup.write_bytes(b"old")
    old_time = time.time() - 31 * 86400
    os.utime(old_backup, (old_time, old_time))
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=backup_dir,
        backup_retention_days=30,
    )
    summary = BatchProcessor(config).run()

    assert summary.backups == 1
    assert summary.backups_deleted == 1
    assert not old_backup.exists()


def test_backup_cleanup_can_be_disabled(
    tmp_path: Path, sample_m4b: Path
) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    old_backup = backup_dir / "old.m4b"
    old_backup.write_bytes(b"old")
    old_time = time.time() - 31 * 86400
    os.utime(old_backup, (old_time, old_time))
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=backup_dir,
        backup_retention_days=0,
    )
    summary = BatchProcessor(config).run()

    assert summary.backups == 1
    assert summary.backups_deleted == 0
    assert old_backup.exists()


def test_backup_of_old_source_is_not_cleaned_immediately(
    tmp_path: Path, make_m4b
) -> None:
    source = make_m4b("old-book.m4b", {"\xa9alb": ["Old Album"]})
    old_time = time.time() - 60 * 86400
    os.utime(source, (old_time, old_time))
    backup_dir = tmp_path / "backup"
    config = _config(
        tmp_path,
        rules=(TagRule("album", "Old Album", "New Album"),),
        backup=True,
        backup_dir=backup_dir,
        backup_retention_days=30,
        overwrite_existing=True,
    )

    first = BatchProcessor(config).run()
    second = BatchProcessor(config).run()

    assert first.backups == 1
    assert first.backups_deleted == 0
    assert second.backups_deleted == 0
    assert (backup_dir / source.name).exists()
