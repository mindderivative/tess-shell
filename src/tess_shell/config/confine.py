"""Where a path written in a shell file may point (Security Model, control 3).

A path in a TDL file (an ``Import:``, a ``Style:``, a ``Source:``, a ``path`` param, an icon file)
is written relative to the file that holds it. It must end inside the configured directories (the
configuration folder and each folder ``Directories`` adds) or inside the package's own ``shipped``
folder, after ``..`` and symbolic links are resolved. :class:`Confinement` is the one place that
decides; every resolution of such a path goes through it. Standard library only.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


class PathOutsideConfig(ValueError):
    """A path a file wrote leaves the configured directories; ``text`` is what the file wrote and
    ``resolved`` where it really points."""

    HINT = (
        "a path may name only files inside the configuration folder (or a folder of "
        "Directories), after .. and symbolic links are resolved"
    )

    def __init__(self, text: str, resolved: str) -> None:
        super().__init__(f"{text} leaves the configuration folders: it points to {resolved}")
        self.text = text
        self.resolved = resolved


@dataclass(frozen=True, slots=True)
class Confinement:
    """The folders a path of a shell file may reach, each as its real path."""

    roots: tuple[str, ...]

    @classmethod
    def of(cls, directories: Iterable[Path], shipped: Path) -> Confinement:
        """The configured ``directories`` and the package's ``shipped`` folder."""
        return cls(tuple(dict.fromkeys(os.path.realpath(d) for d in (*directories, shipped))))

    def contains(self, real: str) -> bool:
        return any(real == root or real.startswith(root + os.sep) for root in self.roots)

    def target(self, file: Path, text: str) -> Path:
        """The absolute path ``text`` names when written in ``file`` (``~`` expanded, ``..`` folded
        away, a symbolic link not followed). Raises :class:`PathOutsideConfig` when it does not
        end inside the roots after the links are followed."""
        absolute = os.path.abspath(file.parent / os.path.expanduser(text))
        real = os.path.realpath(absolute)
        if not self.contains(real):
            raise PathOutsideConfig(text, real)
        return Path(absolute)

    def resolve_path(self, file: Path) -> Callable[[str], str]:
        """``resolve_path`` for the schema: a path written in ``file`` as an absolute one."""
        return lambda text: str(self.target(file, text))

    def read_text(self, file: Path) -> Callable[[str], str]:
        """``read_text`` for the schema: the UTF-8 text of a file named in ``file``."""
        return lambda text: self.target(file, text).read_text(encoding="utf-8")
