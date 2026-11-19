"""``tesserae-shell check`` for the Python of user modules.

``check`` never ran a module's Python, and still does not by default: the findings the module host
makes when it loads a module (a file that does not parse, no class or two classes extending
``Module``, a missing file) are read from the file's syntax tree
(:mod:`tess_shell.modproc.static`), so a bad user module is named before the shell starts.
``--import-modules`` goes one step further and really imports each user module, in a throwaway
process (one at a time, :data:`TIMEOUT` seconds each: :func:`tess_shell.modproc.child.probe`), for
what only running the file finds (an ``ImportError``, an exception at the top level, an
``__init__`` that raises). That runs the top-level code of the modules, which is why it is asked
for.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from tess_shell.modproc.static import inspect_module_file
from tess_shell.modproc.stub import finding_for
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef

TIMEOUT = 5.0  # seconds a module may take to import in ``--import-modules``


class OwnModule(Protocol):
    """A module file of the user's (``files.loader.ModuleFile``)."""

    @property
    def definition(self) -> ModuleDef: ...

    @property
    def shipped(self) -> bool: ...

    @property
    def python(self) -> Path: ...


def import_findings(
    definition: ModuleDef, py_path: Path, timeout: float = TIMEOUT
) -> list[Finding]:
    """Import ``py_path`` in a process of its own and construct the module with a context that
    has no shell behind it; the findings of ``ModuleHost.load`` for what went wrong."""
    env = {k: v for k, v in os.environ.items() if k not in ("NOTIFY_SOCKET", "WATCHDOG_USEC")}
    name = definition.name
    try:
        run = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "tess_shell.modproc.child",
                "--probe",
                str(py_path),
                "--name",
                name,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return [
            Finding(
                str(py_path),
                1,
                1,
                "error",
                "module-import",
                f"{name}: importing the Python took more than {timeout:g} s",
                f"the layout file is {definition.file}",
            )
        ]
    lines = [ln for ln in run.stdout.splitlines() if ln.startswith("{")]
    try:
        result = json.loads(lines[-1])
    except IndexError, ValueError:
        tail = (run.stderr.strip().splitlines() or ["no output"])[-1]
        return [
            Finding(
                str(py_path),
                1,
                1,
                "error",
                "module-import",
                f"{name}: importing the Python ended the process (exit code {run.returncode}): "
                f"{tail}",
                f"the layout file is {definition.file}",
            )
        ]
    if result["ok"]:
        return []
    kind, text, line = result["type"], result["msg"], int(result.get("line") or 1)
    if result["what"] == "init":
        return [Finding(str(py_path), line, 1, "error", "module-init", f"{kind}: {text}")]
    return [
        Finding(
            str(py_path),
            line,
            1,
            "error",
            "module-import",
            f"{name}: importing the Python failed: {kind}: {text}",
            f"the layout file is {definition.file}",
        )
    ]


def module_findings(modules: Iterable[OwnModule], *, import_modules: bool = False) -> list[Finding]:
    """The findings for the Python of every module that is not shipped: from the syntax tree, and
    with ``import_modules`` from a real import of each file that the tree found no fault in."""
    out: list[Finding] = []
    for mf in modules:
        if mf.shipped:
            continue
        info = inspect_module_file(mf.python)
        if info.problems:
            out.extend(finding_for(mf.definition, mf.python, p) for p in info.problems)
        elif import_modules:
            out.extend(import_findings(mf.definition, mf.python))
    return out
