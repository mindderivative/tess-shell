"""A ``Call`` shortcut loads its module (Global Shortcuts, D-052): an instance with no use, so a key
can act without the module on a Bar; started once, shared with a surface that uses it later, and
stopped when neither a surface nor a shortcut names it. A real shell on a private sway and a private
bus with a FAKE ``org.kde.kglobalaccel``; nothing touches the real session."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import test_shortcuts_live as live
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.shell_samples import HEADER
from tests.test_shortcuts_live import Desk, Make

live_desk = (
    live.desk
)  # the fixture of the live shortcut tests: a shell, a private bus, a fake service

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

PROBE_TDL = """
Module {
    Params { token { Type: string, Default: "" } }
    Text { Text: {{ label }} }
}
"""
PROBE_PY = """
from tess_shell import Module, action


class Probe(Module):
    def start(self):
        self.ctx.log.info("probe started")
        self.ctx.send("label", "probe")  # with no use there is nobody to send to

    def stop(self):
        self.ctx.log.info("probe stopped")

    @action
    def mark(self, event, n=0):
        self.ctx.log.info(f"probe marked {n}")
"""
ENTRY = 'Probe_Mark { Keys: "Ctrl+Alt+P", Action: Call, Target: "Probe.mark", n: 3 }'
CLOCK = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'


def setup(d: Desk, settings: str, *, bar_uses_probe: bool = False) -> None:
    d.write(settings)
    folder = d.cfg / "Modules" / "Probe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Probe_Module.tdl").write_text(HEADER.replace("Main_Shell", "Probe") + PROBE_TDL)
    (folder / "Probe_Module.py").write_text(PROBE_PY)
    if bar_uses_probe:
        shell = d.cfg / "Shells" / "Main_Shell.tdl"
        shell.write_text(shell.read_text().replace(CLOCK, 'Probe { token: "x" }'))


def modules(d: Desk) -> list[str]:
    return list(json.loads(d.run("status", "--json").stdout)["modules"])


def shortcuts(*entries: str) -> str:
    return "    Shortcuts {\n" + "\n".join(f"        {e}" for e in entries) + "\n    }"


def test_a_call_shortcut_loads_a_module_no_bar_uses_and_the_press_calls_the_action(
    live_desk: Make,
) -> None:
    d = live_desk()
    setup(d, shortcuts(ENTRY))
    shell = d.start()
    assert shell.stderr.count("probe started") == 1  # loaded and started once, with no use
    assert "call-module-not-loaded" not in shell.stderr and "ERROR" not in shell.stderr
    assert d.fake.names() == ["Probe_Mark"]
    assert d.fake.press_key(d.fake.keys_of("tesserae-shell", "Probe_Mark")[0])
    d.seen("probe marked 3")  # the handler's argument arrived by name
    assert d.finish() == 0
    assert d.log().count("probe started") == 1 and "probe stopped" in d.log()


def test_removing_the_entry_at_reload_stops_the_module_and_adding_it_starts_it_again(
    live_desk: Make,
) -> None:
    d = live_desk()
    setup(d, shortcuts(ENTRY))
    d.start()
    d.seen("probe started")
    d.settings("")
    assert d.run("reload").returncode == 0
    d.seen("module Probe: no longer used, stopped")
    assert d.fake.names() == []
    d.settings(shortcuts(ENTRY))
    assert d.run("reload").returncode == 0
    assert wait_for(lambda: d.log().count("probe started") == 2, 10)
    assert wait_for(lambda: d.fake.names() == ["Probe_Mark"])
    assert d.finish() == 0


def test_a_surface_that_uses_the_module_shares_the_one_instance(live_desk: Make) -> None:
    d = live_desk()
    setup(d, shortcuts(ENTRY))
    d.start()
    d.seen("probe started")
    setup(d, shortcuts(ENTRY), bar_uses_probe=True)  # a Bar now uses Probe as well
    assert d.run("reload").returncode == 0
    assert modules(d) == ["Probe"]  # one module, whatever names it
    d.settings("")  # the shortcut goes: the Bar still uses it, so it keeps running
    assert d.run("reload").returncode == 0
    assert "no longer used" not in d.log() and modules(d) == ["Probe"]
    assert d.finish() == 0


def test_a_surface_that_stops_using_the_module_leaves_it_running_for_the_shortcut(
    live_desk: Make,
) -> None:
    d = live_desk()
    setup(d, shortcuts(ENTRY), bar_uses_probe=True)
    d.start()
    d.seen("probe started")
    setup(d, shortcuts(ENTRY))  # the Bar stops using it; the entry names it
    assert d.run("reload").returncode == 0
    assert "no longer used" not in d.log() and modules(d) == ["Probe"]
    assert d.fake.press_key(d.fake.keys_of("tesserae-shell", "Probe_Mark")[0])
    d.seen("probe marked 3")
    assert d.finish() == 0


def test_a_missing_action_or_a_bad_argument_is_still_a_finding_naming_it(
    live_desk: Make, tmp_path: Path
) -> None:
    d = live_desk()
    setup(
        d,
        shortcuts('Nope { Keys: "Ctrl+Alt+N", Action: Call, Target: "Probe.marc" }'),
    )
    shell = d.start()  # the shell starts: the finding is reported, the action is not registered
    assert "Probe has no action marc" in shell.stderr and "mark" in shell.stderr
    assert d.fake.names() == []
    assert d.finish() == 0
    d2 = live_desk()
    d2.cfg = tmp_path / "cfg2"
    setup(d2, shortcuts('Bad { Keys: "Ctrl+Alt+B", Action: Call, Target: "Probe.mark", m: 1 }'))
    shell2 = d2.start()
    assert "Probe.mark has no argument m" in shell2.stderr
    assert d2.fake.names() == []
    assert d2.finish() == 0
