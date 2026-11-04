"""Find the shell files under the search directories (File Discovery)."""

from __future__ import annotations

import os
from pathlib import Path

from tess_shell.config.settings import Settings

# folder -> file name suffix
SUFFIXES: dict[str, str] = {
    "Shells": "_Shell.tdl",
    "Modules": "_Module.tdl",
    "Styles": "_Style.tdl",
    "Themes": "_Theme.tdl",
    "Stylesheets": "_Stylesheet.tdl",
}
SKIPPED_DIRS = frozenset({"schemas", "logs", "backups"})
SKIPPED_ENDINGS = ("~", ".swp", ".tmp", ".bak")


def shipped_dir() -> Path:
    """The modules that ship with the shell, searched after the user's ``Modules`` folders."""
    return Path(__file__).resolve().parent.parent / "shipped"


def is_shipped(path: Path) -> bool:
    return shipped_dir() in path.parents


def discover(settings: Settings) -> list[Path]:
    """Every shell file under the search directories of each type, once, in a stable order.
    The shipped modules come last, so a user module of the same name can override them."""
    found: dict[Path, None] = {}
    for folder, suffix in SUFFIXES.items():
        roots = list(settings.directories.get(folder, ()))
        if folder == "Modules":
            roots.append(shipped_dir())
        for root in roots:
            for current, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRS)
                for name in sorted(files):
                    if name.startswith(".") or name.endswith(SKIPPED_ENDINGS):
                        continue
                    if name.endswith(suffix):
                        found.setdefault(Path(current) / name, None)
    return list(found)
