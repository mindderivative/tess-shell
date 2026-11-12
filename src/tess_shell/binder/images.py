"""The pixels of a Bitmap (Standard Modules > Image, Block Reference > Bitmap).

The shell decodes an image file and gives tre pixels (data in, not files): ``tess_utils.image``
turns the bytes of a png, jpeg, gif or webp into straight-alpha RGBA8 (an animated gif shows its
first frame). A file that cannot be read or decoded, or that is larger than the limit, shows the
*error image* and is warned about once.

Decoded pixels are cached by the file's path and modification time (and size), so a rebuild of a
surface decodes nothing again, and the cache holds at most :data:`BUDGET` bytes, the least
recently used pixels going first. Decoding is done on the loop thread, on first use (M4 Brief,
question 18: acceptable until a typical decode takes over :data:`SLOW_MS`). Each decode is timed:
``timings`` keeps the last ones, and one over :data:`SLOW_MS` is logged at debug level with the
file's name, so the off-thread route is built when it is measured to be needed.
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from tess_shell._vendor import tess_utils

MAX_SIDE = 4096  # an image larger than this in either side is refused (Standard Modules > Image)
MAX_FILE = 64 * 1024 * 1024  # a file larger than this is not read
BUDGET = 256 * 1024 * 1024  # bytes of decoded pixels the cache keeps
SLOW_MS = 8.0  # a decode on the loop thread over this is logged (about half a 60 Hz frame)
ERROR_IMAGE = Path(__file__).resolve().parent.parent / "shipped" / "Images" / "error.png"


@dataclass(frozen=True, slots=True)
class Pixels:
    """A decoded image: straight-alpha RGBA8, row by row from the top."""

    width: int
    height: int
    rgba: bytes


Key = tuple[str, int, int]  # path, modification time (ns), size


class ImageCache:
    """Decoded images by file; one process-wide instance, :data:`IMAGES`."""

    def __init__(self, budget: int = BUDGET) -> None:
        self.budget = budget
        self._pixels: OrderedDict[Key, Pixels] = OrderedDict()
        self._failed: dict[Key, str] = {}  # keys already warned about, with the reason
        self._error: Pixels | None = None
        self.decoded = 0  # files decoded since the start (a cache hit does not count)
        self.size = 0  # bytes held
        # (path, milliseconds to read and decode it), the last ones: the measurement of question 18
        self.timings: deque[tuple[str, float]] = deque(maxlen=64)

    def clear(self) -> None:
        self._pixels.clear()
        self._failed.clear()
        self.size = 0

    def error_image(self) -> Pixels:
        """The picture a bad file shows: a framed square with a cross, shipped as a png."""
        if self._error is None:
            width, height, rgba = tess_utils.decode_image(ERROR_IMAGE.read_bytes())
            self._error = Pixels(width, height, rgba)
        return self._error

    def load(self, path: str) -> Pixels:
        """The pixels of the image file ``path``; the error image, with one warning, when it
        cannot be had (missing, unreadable, not a png, jpeg, gif or webp, or over the limit)."""
        where = os.path.expanduser(path)
        try:
            stat = os.stat(where)
        except OSError as exc:
            return self._failure((where, 0, 0), f"cannot read the image: {exc.strerror}")
        key = (where, stat.st_mtime_ns, stat.st_size)
        found = self._pixels.get(key)
        if found is not None:
            self._pixels.move_to_end(key)
            return found
        if key in self._failed:
            return self.error_image()
        if stat.st_size > MAX_FILE:
            reason = f"the file is {stat.st_size} bytes, over the limit of {MAX_FILE}"
            return self._failure(key, reason)
        started = time.perf_counter()
        try:
            data = Path(where).read_bytes()
            width, height, rgba = tess_utils.decode_image(data, MAX_SIDE)
        except OSError as exc:
            return self._failure(key, f"cannot read the image: {exc.strerror}")
        except ValueError as exc:
            return self._failure(key, str(exc))
        took = (time.perf_counter() - started) * 1000
        self.timings.append((where, took))
        if took > SLOW_MS:
            logger.debug(
                f"image {where}: decoding {width}x{height} took {took:.1f} ms on the loop "
                f"(over {SLOW_MS:g} ms: the off-thread route is due)"
            )
        self.decoded += 1
        pixels = Pixels(width, height, rgba)
        self._pixels[key] = pixels
        self.size += len(rgba)
        self._trim()
        return pixels

    def _trim(self) -> None:
        while self.size > self.budget and len(self._pixels) > 1:
            _, old = self._pixels.popitem(last=False)
            self.size -= len(old.rgba)

    def _failure(self, key: Key, reason: str) -> Pixels:
        if key not in self._failed:
            self._failed[key] = reason
            logger.warning(f"image {key[0]}: {reason}; showing the error image")
        return self.error_image()


IMAGES = ImageCache()
