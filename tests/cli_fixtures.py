"""Recorded outputs of the command line, for tools that never run the real shell (the tess-ui
configuration application builds its tests on them).

``tests/fixtures/cli/`` holds what ``schema --json``, ``check --json`` and ``version --json`` print,
for a clean folder and for a folder with a finding. ``tests/test_cli_fixtures.py`` proves each file
still equals what the command prints now, so a fixture cannot go stale. Values that change with the
machine or a release (the folder, the versions) are replaced by a ``<...>`` placeholder on both
sides. Rewrite the files after a deliberate change with

    env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.cli_fixtures

``status --json`` has no fixture: ``status`` is not built yet (it needs the control interface).
"""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tess_shell.cli import main

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cli"
CLEAN = FIXTURES / "config_clean"
FINDINGS = FIXTURES / "config_findings"


def run(*argv: str) -> tuple[int, str]:
    """``tesserae-shell ARGV`` in this process: the exit code and what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


def _scrub(value: Any, folder: Path) -> Any:
    """The machine- and release-dependent values of a command's JSON, as placeholders."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "config_dir" and item == str(folder):
                out[key] = "<config_dir>"
            elif key in ("shell", "tess_re", "tess_el", "tess_dl", "python", "shell_version"):
                out[key] = f"<{key}>"
            else:
                out[key] = _scrub(item, folder)
        return out
    if isinstance(value, list):
        return [_scrub(item, folder) for item in value]
    return value


def _command(*argv: str, folder: Path, code: int) -> Callable[[], str]:
    def render() -> str:
        got, text = run(*argv, "--config-dir", str(folder))
        assert got == code, f"{argv} exited {got}, expected {code}"
        return json.dumps(_scrub(json.loads(text), folder), indent=2) + "\n"

    return render


# fixture file -> (the command's exit code, how to print it)
RECORDED: dict[str, Callable[[], str]] = {
    "schema.json": lambda: (
        json.dumps(_scrub(json.loads(run("schema", "--json")[1]), CLEAN), indent=2) + "\n"
    ),
    "check_clean.json": _command("check", "--json", folder=CLEAN, code=0),
    "check_findings.json": _command("check", "--json", folder=FINDINGS, code=1),
    "version.json": _command("version", "--json", folder=CLEAN, code=0),
}


def write() -> None:
    for name, render in RECORDED.items():
        (FIXTURES / name).write_text(render(), encoding="utf-8")
        print(f"wrote {FIXTURES / name}")


if __name__ == "__main__":
    write()
