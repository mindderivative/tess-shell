"""What a module process imports. A process per user module costs about 17 MB; most of it is the
interpreter and loguru, and every module the child pulls in on top is memory times the number of
user modules, so the child's import closure is pinned: nothing of the engine, the D-Bus library, the
shell's services, binder, surfaces or the file parsers."""

from __future__ import annotations

import json
import subprocess
import sys

FORBIDDEN = (
    "tess_re",
    "tess_dl",
    "tess_el",
    "dbus_fast",
    "tess_utils",
    "tess_shell.services.bus",
    "tess_shell.services.layer",
    "tess_shell.surfaces",
    "tess_shell.binder",
    "tess_shell.schema.model",
    "tess_shell.config",
    "tess_shell.app",
    "tess_shell.modules.host",
    "tess_shell.modproc.supervisor",
    "tess_shell.modproc.broker",
)


def test_a_module_process_imports_none_of_the_shells_heavy_parts() -> None:
    code = (
        "import json, sys\nimport tess_shell.modproc.child\nprint(json.dumps(sorted(sys.modules)))"
    )
    run = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    loaded = json.loads(run.stdout)
    heavy = [m for m in loaded if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)]
    assert not heavy, heavy
