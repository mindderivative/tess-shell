"""Files that exist only in memory: the text an editor is holding, as the shell reads its files.

The preview (``tess_shell.preview``) shows what the configuration being edited would give, before
it is saved. Every place that reads a configuration file goes through :func:`read_bytes`,
:func:`is_file`, :func:`is_dir` and :func:`added`; with an overlay set (:func:`overlaid`) a path
the overlay holds is read from it, a path it does not hold from the disk. With none set (the
shell itself) they are the plain file system calls."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_files: ContextVar[Mapping[str, bytes] | None] = ContextVar("tess_shell_overlay", default=None)


def _key(path: Path | str) -> str:
    return os.path.abspath(path)


@contextmanager
def overlaid(files: Mapping[Path, str]) -> Iterator[None]:
    """Read ``files`` (path -> text) instead of the disk's, inside the block, in this thread."""
    token = _files.set({_key(p): text.encode("utf-8") for p, text in files.items()})
    try:
        yield
    finally:
        _files.reset(token)


def read_bytes(path: Path) -> bytes:
    held = _files.get()
    if held is not None:
        data = held.get(_key(path))
        if data is not None:
            return data
    return path.read_bytes()


def exists(path: Path) -> bool:
    return is_file(path) or is_dir(path)


def is_file(path: Path) -> bool:
    held = _files.get()
    return (held is not None and _key(path) in held) or path.is_file()


def is_dir(path: Path) -> bool:
    held = _files.get()
    if held is not None:
        prefix = _key(path) + os.sep
        if any(name.startswith(prefix) for name in held):
            return True
    return path.is_dir()


def added(root: Path) -> list[Path]:
    """The overlay's files under ``root`` (sorted): files the disk may not have."""
    held = _files.get()
    if not held:
        return []
    prefix = _key(root) + os.sep
    return sorted(Path(name) for name in held if name.startswith(prefix))
