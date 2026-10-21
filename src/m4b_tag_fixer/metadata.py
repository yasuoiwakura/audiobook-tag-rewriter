from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from mutagen.mp4 import MP4, MP4FreeForm, MP4MetadataError, MP4Tags

FIELD_MAP: dict[str, str] = {
    "album": "\xa9alb",
    "artist": "\xa9ART",
    "title": "\xa9nam",
    "albumartist": "aART",
    "track": "trkn",
    "year": "\xa9day",
    "genre": "\xa9gen",
    "composer": "\xa9wrt",
    "comment": "\xa9cmt",
    "grouping": "\xa9grp",
    "description": "desc",
    "subtitle": "\xa9st3",
    "publisher": "\xa9pub",
    "series": "tvsh",
    "series-part": "tven",
    "language": "lang",
    "isbn": "----:com.apple.iTunes:ISBN",
    "asin": "----:com.apple.iTunes:ASIN",
}

EXTRA_ATOMS: dict[str, tuple[str, ...]] = {
    "series": ("mvnm",),
    "series-part": ("mvin",),
}

TAG_ALIASES: dict[str, str] = {
    "album-artist": "albumartist",
    "album_artist": "albumartist",
    "author": "artist",
    "narrator": "composer",
    "mvnm": "series",
    "mvin": "series-part",
    "tvsh": "series",
    "tven": "series-part",
    "show": "series",
    "episode_id": "series-part",
    "episode-id": "series-part",
    "series_part": "series-part",
    "lang": "language",
    "audible_asin": "asin",
    "audible-asin": "asin",
}

SUPPORTED_TAGS: tuple[str, ...] = tuple(FIELD_MAP)

FREEFORM_FIELDS = frozenset({"isbn", "asin"})
INTEGER_ATOMS = frozenset({"mvin"})

TEXT_FIELDS: dict[str, str] = {
    name: atom for name, atom in FIELD_MAP.items() if name != "track"
}

DISPLAY_FIELDS: tuple[str, ...] = (
    "album",
    "title",
    "artist",
    "albumartist",
    "composer",
    "track",
    "year",
    "genre",
    "series",
    "series-part",
    "subtitle",
    "publisher",
    "language",
    "description",
    "isbn",
    "asin",
)


def _install_mp4_atom_support() -> None:
    try:
        atoms = MP4Tags._MP4Tags__atoms
        parse_integer = MP4Tags._MP4Tags__parse_integer
        parse_text = MP4Tags._MP4Tags__parse_text
        render_integer = MP4Tags._MP4Tags__render_integer
        render_text = MP4Tags._MP4Tags__render_text
    except AttributeError:
        return

    def parse_series_part(self: MP4Tags, atom, data):
        try:
            return parse_integer(self, atom, data)
        except MP4MetadataError:
            return parse_text(self, atom, data, implicit=False)

    def parse_implicit_text(self: MP4Tags, atom, data):
        return parse_text(self, atom, data, implicit=True)

    atoms[b"mvin"] = (parse_series_part, render_integer, 2)
    for name in (b"mvnm", b"tven", b"tvsh", b"\xa9st3", b"\xa9pub", b"lang"):
        atoms.setdefault(name, (parse_implicit_text, render_text))


_install_mp4_atom_support()


def normalize_tag(name: str) -> str:
    value = name.strip().lower()
    return TAG_ALIASES.get(value, value)


class MetadataError(Exception):
    pass


@dataclass
class TagSnapshot:
    values: dict[str, list[str]] = field(default_factory=dict)
    track_total: int | None = None

    def get(self, tag: str) -> list[str]:
        return self.values.get(tag, [])


@dataclass(frozen=True)
class RuleResult:
    status: Literal["changed", "missing", "mismatch"]
    replaced: int = 0
    current: tuple[str, ...] = ()


@dataclass(frozen=True)
class MappingResult:
    status: Literal["changed", "missing", "same_field", "unchanged"]
    source: str
    target: str
    values: tuple[str, ...] = ()
    previous_target: tuple[str, ...] = ()


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _read_text_values(tags: object, atom: str) -> list[str]:
    raw = tags.get(atom) if tags is not None else None
    if not raw:
        return []
    if not isinstance(raw, (list, tuple)):
        return [_text(raw)]
    return [_text(value) for value in raw]


def _read_field_values(tags: object, name: str) -> list[str]:
    for atom in (FIELD_MAP[name], *EXTRA_ATOMS.get(name, ())):
        values = _read_text_values(tags, atom)
        if values:
            return values
    return []


def read_tags(path: Path) -> TagSnapshot:
    try:
        audio = MP4(path)
    except Exception as exc:
        raise MetadataError(f"MP4/M4B-Metadaten konnten nicht gelesen werden: {exc}") from exc

    tags = audio.tags
    values = {name: _read_field_values(tags, name) for name in TEXT_FIELDS}

    track_values: list[str] = []
    track_total: int | None = None
    raw_track = tags.get("trkn") if tags is not None else None
    if raw_track:
        entry = raw_track[0]
        if isinstance(entry, (tuple, list)) and len(entry) >= 2:
            track_number, total = int(entry[0]), int(entry[1])
            if track_number != 0 or total != 0:
                track_values.append(str(track_number))
            if total > 0:
                track_total = total
        else:
            track_values.append(_text(entry))

    values["track"] = track_values
    return TagSnapshot(values=values, track_total=track_total)


def apply_mapping(snapshot: TagSnapshot, source: str, target: str) -> MappingResult:
    source = normalize_tag(source)
    target = normalize_tag(target)
    values = snapshot.get(source)

    if not values:
        return MappingResult(status="missing", source=source, target=target)
    if source == target:
        return MappingResult(
            status="same_field", source=source, target=target, values=tuple(values)
        )

    previous_target = tuple(snapshot.get(target))
    if list(previous_target) == values:
        return MappingResult(
            status="unchanged",
            source=source,
            target=target,
            values=tuple(values),
            previous_target=previous_target,
        )

    snapshot.values[target] = list(values)
    return MappingResult(
        status="changed",
        source=source,
        target=target,
        values=tuple(values),
        previous_target=previous_target,
    )


def apply_rule(snapshot: TagSnapshot, tag: str, old: str, new: str) -> RuleResult:
    tag = normalize_tag(tag)
    current = list(snapshot.get(tag))
    if not current:
        return RuleResult(status="missing")

    matches = [index for index, value in enumerate(current) if value == old]
    if not matches:
        return RuleResult(status="mismatch", current=tuple(current))

    for index in matches:
        current[index] = new
    snapshot.values[tag] = current
    return RuleResult(status="changed", replaced=len(matches), current=tuple(current))


def format_tags(snapshot: TagSnapshot) -> str:
    parts = []
    for name in DISPLAY_FIELDS:
        values = snapshot.get(name)
        shown = ", ".join(values) if values else "<nicht gesetzt>"
        parts.append(f"{name}={shown}")
    return "; ".join(parts)


def write_changes(
    path: Path, snapshot: TagSnapshot, changed_fields: Iterable[str]
) -> None:
    changed = {normalize_tag(name) for name in changed_fields}
    if not changed:
        return

    try:
        audio = MP4(path)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        assert tags is not None

        for name in changed:
            if name == "track":
                values = snapshot.get("track")
                if not values:
                    continue
                track_number = int(values[0])
                total = snapshot.track_total or 0
                tags["trkn"] = [(track_number, total)]
                continue

            values = list(snapshot.get(name))
            atoms = (FIELD_MAP[name], *EXTRA_ATOMS.get(name, ()))

            for atom in atoms:
                if name in FREEFORM_FIELDS:
                    tags[atom] = [
                        MP4FreeForm(value.encode("utf-8")) for value in values
                    ]
                elif atom in INTEGER_ATOMS:
                    if not values:
                        continue
                    if not values[0].strip().isdigit():
                        raise MetadataError(
                            f"Tag {name!r} erwartet eine ganze Zahl, erhalten: {values[0]!r}"
                        )
                    tags[atom] = [int(values[0])]
                else:
                    tags[atom] = values

        audio.save()
    except MetadataError:
        raise
    except Exception as exc:
        raise MetadataError(f"MP4/M4B-Metadaten konnten nicht geschrieben werden: {exc}") from exc
