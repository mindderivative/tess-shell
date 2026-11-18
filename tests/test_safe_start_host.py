"""Safe start in the module host (Crash Recovery and Watchdog > A Crash Loop): a user module's
Python is not run, a shipped module's is, nothing is reported as an error, and a reload the user
asks for ends it."""

from __future__ import annotations

from pathlib import Path

from tess_shell.binder.model import Handler
from tess_shell.config.discovery import shipped_dir
from tess_shell.modules.host import LoadedModule, ModuleHost
from tess_shell.schema.findings import Finding
from tests.test_module_host import Rig, definition, use

RAN = """
from pathlib import Path
from tess_shell import Module, action

Path({marker!r}).write_text("imported")

class Mine(Module):
    @action
    def go(self, event):
        pass
"""


def user_module(rig: Rig, name: str = "Mine") -> tuple[Path, Path]:
    marker = rig.tmp / f"{name}.imported"
    py = rig.tmp / f"{name}_Module.py"
    py.write_text(RAN.replace("Mine", name).format(marker=str(marker)))
    return py, marker


def load(
    host: ModuleHost, py: Path, name: str = "Mine"
) -> tuple[LoadedModule | None, list[Finding]]:
    return host.load(definition(name), py, f"uid-{name}", [use(name)])


def test_a_user_module_is_not_imported_and_nothing_is_reported(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.host.safe_start = True
    py, marker = user_module(rig)
    loaded, findings = load(rig.host, py)
    assert loaded is None and findings == []
    assert not marker.exists(), "the Python of a user module ran in a safe start"
    assert rig.host.safe_skipped == ["Mine"] and "Mine" not in rig.host.loaded


def test_a_shipped_module_still_loads_in_a_safe_start(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.host.safe_start = True
    clock_py = shipped_dir() / "Clock" / "Clock_Module.py"
    assert clock_py.is_file()
    loaded, findings = rig.host.load(definition("Clock"), clock_py, "uid-clock", [use("Clock")])
    assert loaded is not None and findings == []
    assert rig.host.safe_skipped == []


def test_a_call_to_a_module_that_was_skipped_is_not_an_error_but_a_missing_one_still_is(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    rig.host.safe_start = True
    py, _ = user_module(rig)
    load(rig.host, py)
    skipped = Handler("go", module="Mine")
    other = Handler("go", module="Nobody")
    rules = [f.rule for f in rig.host.check_calls([skipped, other])]
    assert rules == ["call-module-not-loaded"]  # only for the module nobody has


def test_a_reload_the_user_asked_for_ends_it_and_the_module_loads_then(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.host.safe_start = True
    py, marker = user_module(rig)
    load(rig.host, py)
    rig.host.end_safe_start()
    assert rig.host.safe_start is False and rig.host.safe_skipped == []
    loaded, findings = load(rig.host, py)
    assert loaded is not None and findings == [] and marker.exists()


def test_a_normal_start_runs_the_same_module(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    py, marker = user_module(rig)
    loaded, _ = load(rig.host, py)
    assert loaded is not None and marker.exists()
