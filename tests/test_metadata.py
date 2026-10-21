from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

from m4b_tag_fixer.metadata import (
    MetadataError,
    apply_mapping,
    apply_rule,
    format_tags,
    normalize_tag,
    read_tags,
    write_changes,
)


def test_reads_mp4_tags(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)

    assert snapshot.get("album") == ["Old Album"]
    assert snapshot.get("artist") == ["Old Author"]
    assert snapshot.get("title") == ["Old Title"]
    assert snapshot.get("albumartist") == ["Old Album Artist"]
    assert snapshot.get("track") == ["3"]
    assert snapshot.track_total == 12
    assert snapshot.get("year") == ["2020"]
    assert snapshot.get("genre") == ["Audiobook"]
    assert snapshot.get("comment") == []


def test_missing_tags_are_not_an_error(make_m4b) -> None:
    path = make_m4b("empty.m4b")
    snapshot = read_tags(path)

    assert snapshot.get("album") == []
    assert snapshot.get("track") == []
    assert snapshot.track_total is None
    assert "<nicht gesetzt>" in format_tags(snapshot)


def test_corrupt_file_raises_metadata_error(make_m4b, tmp_path: Path) -> None:
    path = tmp_path / "broken.m4b"
    path.write_bytes(b"this is not an mp4 file")

    with pytest.raises(MetadataError):
        read_tags(path)


def test_exact_match_only_no_substring_replacement(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)

    substring = apply_rule(snapshot, "album", "Old", "New")
    assert substring.status == "mismatch"
    assert snapshot.get("album") == ["Old Album"]

    exact = apply_rule(snapshot, "album", "Old Album", "New Album")
    assert exact.status == "changed"
    assert snapshot.get("album") == ["New Album"]


def test_missing_tag_is_reported(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)
    result = apply_rule(snapshot, "comment", "irrelevant", "new comment")

    assert result.status == "missing"


def test_multiple_values_only_matching_values_are_replaced(make_m4b) -> None:
    path = make_m4b("multi.m4b", {"\xa9ART": ["Author A", "Author B"]})
    snapshot = read_tags(path)

    result = apply_rule(snapshot, "artist", "Author A", "Author C")

    assert result.status == "changed"
    assert result.replaced == 1
    assert snapshot.get("artist") == ["Author C", "Author B"]


def test_rules_are_applied_sequentially(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)

    assert apply_rule(snapshot, "album", "Old Album", "Intermediate").status == "changed"
    assert apply_rule(snapshot, "album", "Intermediate", "Final").status == "changed"
    assert snapshot.get("album") == ["Final"]


def test_track_change_preserves_total(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)

    result = apply_rule(snapshot, "track", "3", "7")

    assert result.status == "changed"
    assert snapshot.get("track") == ["7"]
    assert snapshot.track_total == 12


def test_write_changes_preserves_other_tags(sample_m4b: Path, tmp_path: Path) -> None:
    snapshot = read_tags(sample_m4b)
    apply_rule(snapshot, "album", "Old Album", "New Album")
    apply_rule(snapshot, "track", "3", "4")

    output = tmp_path / "out" / "book.m4b"
    output.parent.mkdir()
    shutil.copy2(sample_m4b, output)

    write_changes(output, snapshot, {"album", "track"})
    result = read_tags(output)

    assert result.get("album") == ["New Album"]
    assert result.get("track") == ["4"]
    assert result.track_total == 12
    assert result.get("artist") == ["Old Author"]
    assert result.get("title") == ["Old Title"]
    assert result.get("albumartist") == ["Old Album Artist"]
    assert result.get("year") == ["2020"]
    assert result.get("genre") == ["Audiobook"]


def test_write_changes_with_no_fields_is_a_noop(sample_m4b: Path, tmp_path: Path) -> None:
    output = tmp_path / "copy.m4b"
    shutil.copy2(sample_m4b, output)
    before = output.read_bytes()

    write_changes(output, read_tags(output), set())

    assert output.read_bytes() == before


def test_write_changes_preserves_cover_and_freeform_atoms(make_m4b, tmp_path: Path) -> None:
    cover = MP4Cover(b"\x89PNG\r\n\x1a\ncover", imageformat=MP4Cover.FORMAT_PNG)
    freeform = MP4FreeForm(b"custom value")
    path = make_m4b(
        "extra.m4b",
        {
            "\xa9alb": ["Old Album"],
            "covr": [cover],
            "----:com.apple.iTunes:TEST": [freeform],
            "tmpo": [120],
        },
    )
    snapshot = read_tags(path)
    apply_rule(snapshot, "album", "Old Album", "New Album")

    output = tmp_path / "extra-copy.m4b"
    shutil.copy2(path, output)
    write_changes(output, snapshot, {"album"})

    tags = MP4(output).tags
    assert tags is not None
    assert bytes(tags["covr"][0]) == bytes(cover)
    assert bytes(tags["----:com.apple.iTunes:TEST"][0]) == bytes(freeform)
    assert tags["tmpo"] == [120]
    assert tags["\xa9alb"] == ["New Album"]


def test_default_mapping_writes_series_and_series_part(
    sample_m4b: Path, tmp_path: Path
) -> None:
    snapshot = read_tags(sample_m4b)

    assert apply_mapping(snapshot, "album", "series").status == "changed"
    assert apply_mapping(snapshot, "track", "series-part").status == "changed"
    assert apply_mapping(snapshot, "title", "album").status == "changed"

    output = tmp_path / "mapped.m4b"
    shutil.copy2(sample_m4b, output)
    write_changes(output, snapshot, {"series", "series-part", "album"})
    result = read_tags(output)

    assert result.get("title") == ["Old Title"]
    assert result.get("album") == ["Old Title"]
    assert result.get("series") == ["Old Album"]
    assert result.get("series-part") == ["3"]
    assert result.get("track") == ["3"]


def test_mapping_missing_source_is_reported(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)
    result = apply_mapping(snapshot, "publisher", "series")

    assert result.status == "missing"
    assert snapshot.get("series") == []


def test_mapping_to_existing_equal_target_is_unchanged(sample_m4b: Path) -> None:
    snapshot = read_tags(sample_m4b)
    snapshot.values["series"] = ["Old Album"]

    result = apply_mapping(snapshot, "album", "series")

    assert result.status == "unchanged"


def test_mapping_overwrites_target_and_reports_previous_value(
    sample_m4b: Path,
) -> None:
    snapshot = read_tags(sample_m4b)
    snapshot.values["series"] = ["Old Series"]

    result = apply_mapping(snapshot, "album", "series")

    assert result.status == "changed"
    assert result.previous_target == ("Old Series",)
    assert snapshot.get("series") == ["Old Album"]


def test_series_part_is_written_as_integer(make_m4b, tmp_path: Path) -> None:
    source = make_m4b("series.m4b", {"\xa9nam": ["Book"]})
    snapshot = read_tags(source)
    snapshot.values["series-part"] = ["7"]

    output = tmp_path / "series-copy.m4b"
    shutil.copy2(source, output)
    write_changes(output, snapshot, {"series-part"})

    assert read_tags(output).get("series-part") == ["7"]


def test_freeform_isbn_and_asin(make_m4b, tmp_path: Path) -> None:
    source = make_m4b("ids.m4b", {"\xa9nam": ["Book"]})
    snapshot = read_tags(source)
    snapshot.values["isbn"] = ["9781234567890"]
    snapshot.values["asin"] = ["B012345678"]

    output = tmp_path / "ids-copy.m4b"
    shutil.copy2(source, output)
    write_changes(output, snapshot, {"isbn", "asin"})

    result = read_tags(output)
    assert result.get("isbn") == ["9781234567890"]
    assert result.get("asin") == ["B012345678"]


def test_tag_aliases() -> None:
    assert normalize_tag("MVNM") == "series"
    assert normalize_tag("mvin") == "series-part"
    assert normalize_tag("show") == "series"
    assert normalize_tag("episode_id") == "series-part"
    assert normalize_tag("album-artist") == "albumartist"
    assert normalize_tag("audible_asin") == "asin"


def test_writes_abs_and_legacy_series_atoms(make_m4b, tmp_path: Path) -> None:
    source = make_m4b(
        "atoms.m4b",
        {
            "\xa9alb": ["Old Album"],
            "\xa9nam": ["Book Title"],
            "trkn": [(3, 0)],
        },
    )
    snapshot = read_tags(source)
    apply_mapping(snapshot, "album", "series")
    apply_mapping(snapshot, "track", "series-part")
    apply_mapping(snapshot, "title", "album")

    output = tmp_path / "atoms-copy.m4b"
    shutil.copy2(source, output)
    write_changes(output, snapshot, {"series", "series-part", "album"})

    tags = MP4(output).tags
    assert tags is not None
    assert tags["tvsh"] == ["Old Album"]
    assert tags["mvnm"] == ["Old Album"]
    assert tags["tven"] == ["3"]
    assert tags["mvin"] == [3]
    assert tags["\xa9alb"] == ["Book Title"]


def test_reads_legacy_mvnm_mvin_when_tvsh_tven_are_absent(make_m4b) -> None:
    path = make_m4b("legacy-series.m4b", {"mvnm": ["Legacy Series"], "mvin": [9]})

    snapshot = read_tags(path)

    assert snapshot.get("series") == ["Legacy Series"]
    assert snapshot.get("series-part") == ["9"]


def test_tvsh_tven_have_read_priority(make_m4b) -> None:
    path = make_m4b(
        "both-series.m4b",
        {
            "tvsh": ["ABS Series"],
            "tven": ["5"],
            "mvnm": ["Legacy Series"],
            "mvin": [9],
        },
    )

    snapshot = read_tags(path)

    assert snapshot.get("series") == ["ABS Series"]
    assert snapshot.get("series-part") == ["5"]
