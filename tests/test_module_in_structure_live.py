"""A module call in a ``For`` in a running shell on a private sway: the uses made for the entries
survive a reload that changes the layout or the module's code, and end with the shell (Module File
> Using a Module in a Structure)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.shell_samples import HEADER
from tests.test_reload_live import Make, live  # noqa: F401

pytestmark = pytest.mark.tre

ROWS_TDL = (
    HEADER.replace("Main_Shell", "Rows") + "Module { FlexBox { Name: Root, Spacing: %d, Children { "
    "For r In {{ rows }} Key {{ r.id }} { Pill { title: {{ r.t }} } } } } }\n"
)
ROWS_PY = """
from tess_shell import Module

class Rows(Module):
    def start(self):
        self.ctx.log.info("rows started")
        self.ctx.send("rows", [{"id": "a", "t": "A"}, {"id": "b", "t": "B"}])
"""
PILL_TDL = (
    HEADER.replace("Main_Shell", "Pill")
    + "Module { Params { title { Type: string, Default: none } }\n"
    "FlexBox { Name: Root, Children { Text { Name: T, Text: {{ label }} } } } }\n"
)
PILL_PY = """
from tess_shell import Module

class Pill(Module):
    def start(self):
        self.ctx.log.info(f"pill {VERSION} started with {len(self.ctx.uses)} uses")
        for use in self.ctx.uses.values():
            self.ctx.send("label", use.params["title"] + "{VERSION}", use=use)

    def use_added(self, use):
        self.ctx.log.info(f"pill use added {use.params['title']}")
        self.ctx.send("label", use.params["title"] + "{VERSION}", use=use)

    def use_removed(self, use):
        self.ctx.log.info(f"pill use removed {use.params['title']}")

    def stop(self):
        self.ctx.log.info("pill {VERSION} stopped")
"""


def write(cfg: Path, name: str, tdl: str, py: str) -> None:
    folder = cfg / "Modules" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}_Module.tdl").write_text(tdl)
    (folder / f"{name}_Module.py").write_text(py)


def pill_py(version: str) -> str:
    return PILL_PY.replace("{VERSION}", version)


def test_the_uses_of_a_for_survive_reloads_and_end_with_the_shell(
    live: Make,  # noqa: F811
    tmp_path: Path,
) -> None:
    write(tmp_path, "Rows", ROWS_TDL % 4, ROWS_PY)
    write(tmp_path, "Pill", PILL_TDL, pill_py("v1"))
    run = live(children="Rows { }")
    run.wait("pill v1 started with 0 uses")  # Pill is loaded though no file calls it
    run.wait("pill use added A")
    run.wait("pill use added B")
    assert run.count("pill use added") == 2
    # the Rows layout changes: the entries keep their uses (nobody is told they went)
    write(tmp_path, "Rows", ROWS_TDL % 9, ROWS_PY)
    run.wait(r"reloaded \(", 1)
    assert run.count("pill use removed") == 0 and run.count("pill use added") == 2
    assert "| ERROR " not in run.text()
    # Pill's code changes: the new instance is made with the entries' uses
    write(tmp_path, "Pill", PILL_TDL, pill_py("v2"))
    run.wait("pill v2 started with 2 uses")
    assert run.count("pill use added") == 2  # the new instance was given them at start
    assert run.count("pill v1 stopped") == 1
    assert run.stop() == 0
    assert "| ERROR " not in run.text(), run.text()
