"""The warning ``insecure-permissions`` (Security Model, control 2).

Write access to a module's Python is code execution as the user, so a configuration folder, a
module folder or a module file that group or others can write to, or that another user owns, is
worth a warning. It is a warning and not an error: a shared or network home must still start.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from pathlib import Path

from tess_shell.schema.findings import Finding

RULE = "insecure-permissions"


def permission_findings(paths: Iterable[Path], uid: int | None = None) -> list[Finding]:
    """One warning for each of ``paths`` (once, however many times it is listed) that is writable
    by group or others or not owned by ``uid`` (the current user). A path that does not exist is
    skipped: the file checks say so. A symbolic link is judged by what it points to."""
    me = os.getuid() if uid is None else uid
    out: list[Finding] = []
    seen: set[str] = set()
    for path in paths:
        name = str(path)
        if name in seen:
            continue
        seen.add(name)
        try:
            info = path.stat()
        except OSError:
            continue
        problems: list[str] = []
        mode = stat.S_IMODE(info.st_mode)
        writers = [
            who for who, bit in (("group", stat.S_IWGRP), ("others", stat.S_IWOTH)) if mode & bit
        ]
        if writers:
            problems.append(f"writable by {' and '.join(writers)}")
        if info.st_uid != me:
            problems.append("not owned by you")
        if not problems:
            continue
        kind = "folder" if stat.S_ISDIR(info.st_mode) else "file"
        out.append(
            Finding(
                name,
                1,
                1,
                "warning",
                RULE,
                f"the {kind} {name} is {' and '.join(problems)} (mode {mode:04o}): "
                "write access to a module's Python is code execution as you",
                f"make it yours alone: chmod go-w {name}"
                if writers
                else f"take it over: chown $USER {name}",
            )
        )
    return out
