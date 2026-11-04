"""Where the configuration lives, and how a path written in a shell file is read."""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path

from tess_shell.exit_codes import EnvironmentFailure

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


def check_runtime_dir(
    environ: Mapping[str, str] | None = None, uid: int | None = None
) -> tuple[Path, bool]:
    """Validate ``$XDG_RUNTIME_DIR``. Returns ``(path, loose)``; ``loose`` is true when its mode
    is not 0o700 (a warning, not a failure). Raises ``EnvironmentFailure`` otherwise."""
    env = os.environ if environ is None else environ
    uid = os.getuid() if uid is None else uid
    raw = env.get("XDG_RUNTIME_DIR", "")
    if not raw:
        raise EnvironmentFailure("XDG_RUNTIME_DIR is not set")
    if not os.path.isabs(raw):
        raise EnvironmentFailure(f"XDG_RUNTIME_DIR is not an absolute path: {raw}")
    try:
        info = os.stat(raw)
    except OSError as exc:
        raise EnvironmentFailure(f"XDG_RUNTIME_DIR {raw} cannot be used: {exc.strerror}") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise EnvironmentFailure(f"XDG_RUNTIME_DIR {raw} is not a directory")
    if info.st_uid != uid:
        raise EnvironmentFailure(f"XDG_RUNTIME_DIR {raw} is not owned by the current user")
    return Path(raw), stat.S_IMODE(info.st_mode) != 0o700
