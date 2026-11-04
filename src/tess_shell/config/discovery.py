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


def discover(settings: Settings) -> list[Path]:
    """Every shell file under the search directories of each type, once, in a stable order."""
    found: dict[Path, None] = {}
    for folder, suffix in SUFFIXES.items():
        for root in settings.directories.get(folder, ()):
            for current, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRS)
                for name in sorted(files):
                    if name.startswith(".") or name.endswith(SKIPPED_ENDINGS):
                        continue
                    if name.endswith(suffix):
                        found.setdefault(Path(current) / name, None)
    return list(found)
