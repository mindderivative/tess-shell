"""Read the 8-bit RGBA PNGs that ``tess_re.snapshot.write_png`` writes (filter 0 only)."""

from __future__ import annotations

import struct
import zlib


def decode(data: bytes) -> tuple[bytes, int, int]:
    """Only what ``write_png`` writes: RGBA, 8 bits, no interlace, filter type 0."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
            assert body[8:] == bytes([8, 6, 0, 0, 0])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4 + 1
    out = bytearray()
    for y in range(height):
        assert raw[y * stride] == 0
        out += raw[y * stride + 1 : (y + 1) * stride]
    return bytes(out), width, height
