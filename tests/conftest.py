from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import pytest
from mutagen.mp4 import MP4


def _atom(name: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + name + payload


def _full_atom(version: int = 0, flags: int = 0) -> bytes:
    return struct.pack(">B", version) + flags.to_bytes(3, "big")


def _minimal_mvhd() -> bytes:
    payload = (
        _full_atom()
        + struct.pack(">IIII", 0, 0, 1000, 0)
        + struct.pack(">I", 0x00010000)
        + struct.pack(">H", 0x0100)
        + b"\x00" * 10
        + struct.pack(
            ">9I",
            0x00010000,
            0,
            0,
            0,
            0x00010000,
            0,
            0,
            0,
            0x40000000,
        )
        + b"\x00" * 24
        + struct.pack(">I", 0)
    )
    return _atom(b"mvhd", payload)


def create_m4b(path: Path, tags: dict[str, Any] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ftyp = _atom(b"ftyp", b"M4A " + struct.pack(">I", 0) + b"M4A " + b"isom")
    moov = _atom(b"moov", _minimal_mvhd())
    path.write_bytes(ftyp + moov)

    if tags:
        audio = MP4(path)
        for key, value in tags.items():
            audio[key] = value
        audio.save()
    return path


STANDARD_TAGS: dict[str, Any] = {
    "\xa9alb": ["Old Album"],
    "\xa9ART": ["Old Author"],
    "\xa9nam": ["Old Title"],
    "aART": ["Old Album Artist"],
    "trkn": [(3, 12)],
    "\xa9day": ["2020"],
    "\xa9gen": ["Audiobook"],
}


@pytest.fixture
def make_m4b(tmp_path: Path):
    def factory(name: str, tags: dict[str, Any] | None = None) -> Path:
        target = tmp_path / "input" / name
        return create_m4b(target, tags)

    return factory


@pytest.fixture
def sample_m4b(make_m4b) -> Path:
    return make_m4b("book.m4b", STANDARD_TAGS)
