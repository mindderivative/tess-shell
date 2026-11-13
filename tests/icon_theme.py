"""A temporary freedesktop icon theme on disk, for the icon service and the Tray (Tray Module >
Icons): ``write_theme`` makes ``<base>/<name>/index.theme`` and its directories, ``png_bytes`` a
valid png of one colour. Never reads or writes a real theme folder."""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


def png_bytes(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    """An 8-bit RGBA png of one colour."""
    row = b"\x00" + bytes(rgba) * width

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def svg(fill: str = "#ff0000") -> str:
    """A small SVG document with one filled square."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">'
        f'<rect width="16" height="16" fill="{fill}"/></svg>'
    )


@dataclass(frozen=True, slots=True)
class Dir:
    """One directory of a theme: ``path`` under the theme, its ``Size``, ``Type`` and the files
    in it (a file name to its bytes)."""

    path: str
    size: int
    kind: str = "Fixed"
    files: Mapping[str, bytes | str] | None = None
    minimum: int | None = None
    maximum: int | None = None


def write_theme(base: Path, name: str, dirs: Sequence[Dir], inherits: Sequence[str] = ()) -> Path:
    """``<base>/<name>`` with an ``index.theme`` listing ``dirs``, and every file in them."""
    root = base / name
    root.mkdir(parents=True, exist_ok=True)
    lines = ["[Icon Theme]", f"Name={name}", "Directories=" + ",".join(d.path for d in dirs)]
    if inherits:
        lines.append("Inherits=" + ",".join(inherits))
    for d in dirs:
        lines += ["", f"[{d.path}]", f"Size={d.size}", f"Type={d.kind}"]
        if d.minimum is not None:
            lines.append(f"MinSize={d.minimum}")
        if d.maximum is not None:
            lines.append(f"MaxSize={d.maximum}")
        folder = root / d.path
        folder.mkdir(parents=True, exist_ok=True)
        for filename, content in (d.files or {}).items():
            target = folder / filename
            if isinstance(content, str):
                target.write_text(content, encoding="utf-8")
            else:
                target.write_bytes(content)
    (root / "index.theme").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root
