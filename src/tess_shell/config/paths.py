"""Where the configuration lives, and how a path written in a shell file is read."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

FOLDERS = ("Shells", "Modules", "Styles", "Themes", "Stylesheets", "Icons")

_VARIABLE = re.compile(r"\$(\w+|\{[^}]*\})")


def config_dir(override: Path | None = None, environ: Mapping[str, str] | None = None) -> Path:
    """``--config-dir``, else ``$XDG_CONFIG_HOME/tesserae-shell``, else ``~/.config/...``."""
    if override is not None:
        return Path(os.path.abspath(override))
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_CONFIG_HOME", "")
    if xdg and os.path.isabs(xdg):
        return Path(xdg) / "tesserae-shell"
    return Path.home() / ".config" / "tesserae-shell"


def ensure_config_dir(path: Path) -> None:
    """Create the config directory and its default folders."""
    path.mkdir(parents=True, exist_ok=True)
    for folder in FOLDERS:
        (path / folder).mkdir(exist_ok=True)


class PathError(ValueError):
    """A path that cannot be resolved; the text says what failed."""


def expand_path(text: str) -> str:
    """Expand ``~`` and ``$NAME`` / ``${NAME}``; a leftover of either is a ``PathError``."""
    expanded = os.path.expandvars(os.path.expanduser(text))
    if expanded.startswith("~"):
        raise PathError("the home directory could not be found for '~'")
    leftover = _VARIABLE.search(expanded)
    if leftover:
        raise PathError(f"the variable {leftover.group(0)} is not set")
    return expanded
