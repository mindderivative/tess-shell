"""A real shell on a private headless sway and a private session bus, driven by the
``tesserae-shell`` control commands (IPC and CLI, Acceptance Criteria)."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, FakeBus
from tests.shell_samples import BODY, HEADER, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

LAUNCHER = (
    "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 600, Height: 400, "
    "Visible: false }"
)
SECRET = "hunter2-not-for-status"

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
        self.ctx.send("label", "probe")

    @action
    def add(self, event, a, b):
        return a + b

    @action
    def where(self, event):
        return {"args": dict(event.args)}

    @action
    def fail(self, event):
        raise RuntimeError("probe failed on purpose")

    def not_an_action(self):
        return "reached"
"""


def write_config(cfg: Path, *, control: bool = True, probe: bool = True) -> None:
    body = BODY.replace("            Bar {", f"            {LAUNCHER}\n            Bar {{", 1)
    if probe:
        body = body.replace(
            'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }',
            f'Probe {{ token: "{SECRET}" }}',
        )
    write_example(cfg, body)
    extra = "" if control else "Control: false,"
    (cfg / "settings.tdl").write_text(
        f"---\nTDL: 0.1\nName: S\n---\nSettings {{ {extra} Logging {{ Level: DEBUG }} }}\n"
    )
    if probe:
        folder = cfg / "Modules" / "Probe"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Probe_Module.tdl").write_text(HEADER.replace("Main_Shell", "Probe") + PROBE_TDL)
        (folder / "Probe_Module.py").write_text(PROBE_PY)


class Desk:
    """A running shell, its bus and the ways to run the commands against it."""

    def __init__(self, sway: PrivateSway, bus: FakeBus, cfg: Path) -> None:
        self.sway, self.bus, self.cfg = sway, bus, cfg
        self.env = {**sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address}
        self.shell: Shell | None = None

    def start(self, *extra: str) -> Shell:
        self.shell = Shell(self.cfg, self.env, *extra)
        self.shell.wait_for("running")
        return self.shell

    def run(self, *argv: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tess_shell", *argv],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def seen(self, needle: str, timeout: float = 8) -> None:
        assert self.shell is not None
        self.shell.wait_for(needle, timeout)

    def finish(self) -> int:
        assert self.shell is not None
        if self.shell.process.poll() is None:
            self.shell.process.send_signal(signal.SIGTERM)
        return self.shell.finish()


Make = Callable[..., Desk]


@pytest.fixture
def desk(private_sway: PrivateSway, tmp_path: Path) -> Iterator[Make]:
    made: list[tuple[Desk, FakeBus]] = []

    def make(**kwargs: bool) -> Desk:
        bus = FakeBus()
        write_config(tmp_path / "cfg", **kwargs)
        item = Desk(private_sway, bus, tmp_path / "cfg")
        made.append((item, bus))
        return item

    yield make
    for item, bus in made:
        if item.shell is not None and item.shell.process.poll() is None:
            item.shell.process.kill()
            item.shell.process.wait()
        bus.close()


def test_show_hide_and_toggle_change_the_surface_of_a_real_shell(desk: Make) -> None:
    d = desk()
    d.start()
    assert "hidden, surface kept" in "".join(d.shell.seen if d.shell else [])
    shown = d.run("show", "Launcher")
    assert (shown.returncode, shown.stdout.strip()) == (0, "Launcher is shown")
    d.seen("Panel Launcher on HEADLESS-1 shown")
    again = d.run("show", "Launcher")  # idempotent
    assert (again.returncode, again.stdout.strip()) == (0, "Launcher is shown")
    hidden = d.run("hide", "Launcher")
    assert (hidden.returncode, hidden.stdout.strip()) == (0, "Launcher is hidden")
    d.seen("Panel Launcher on HEADLESS-1 hidden")
    assert d.run("hide", "Launcher").returncode == 0  # idempotent
    toggled = d.run("toggle", "Launcher")
    assert toggled.stdout.strip() == "Launcher is shown"
    assert d.run("toggle", "Launcher").stdout.strip() == "Launcher is hidden"
    assert d.finish() == 0
    log = d.shell.log_text() if d.shell else ""
    assert log.count("Panel Launcher on HEADLESS-1 shown") >= 2


def test_an_unknown_name_gets_the_nearest_names_and_a_bar_cannot_be_hidden(desk: Make) -> None:
    d = desk()
    d.start()
    near = d.run("show", "Launchr")
    assert near.returncode == 1 and "did you mean Launcher" in near.stderr
    nothing = d.run("hide", "Zzz")
    assert nothing.returncode == 1 and "Launcher" in nothing.stderr and "Top_Bar" in nothing.stderr
    bar = d.run("hide", "Top_Bar")
    assert bar.returncode == 1 and "cannot be hidden" in bar.stderr
    assert d.run("show", "Top_Bar").returncode == 0
    assert d.finish() == 0


def test_status_names_the_surfaces_and_modules_and_no_value(desk: Make) -> None:
    d = desk()
    d.start()
    out = d.run("status", "--json")
    assert out.returncode == 0
    status = json.loads(out.stdout)
    assert status["state"] == "running"
    assert {s["name"]: (s["kind"], s["shown"]) for s in status["surfaces"]} == {
        "Launcher": ("panel", False),
        "Top_Bar": ("bar", True),
    }
    assert status["monitors"] == [{"name": "Main", "output": "HEADLESS-1"}]
    assert status["modules"] == ["Probe"]
    assert set(status["version"]) == {"shell", "tess_re", "tess_el", "tess_dl", "python"}
    assert status["errors"] == []
    # no param value, and no line of the log
    assert SECRET not in out.stdout
    assert "14:05" not in out.stdout and "started" not in out.stdout
    text = d.run("status")
    assert text.returncode == 0 and "Top_Bar  bar  shown" in text.stdout
    assert SECRET not in text.stdout
    assert d.finish() == 0


def test_call_runs_an_action_and_refuses_what_is_not_one(desk: Make) -> None:
    d = desk()
    d.start()
    ok = d.run("--json", "call", "Probe", "add", "2", "3")
    assert (ok.returncode, json.loads(ok.stdout)) == (0, {"ok": True, "result": 5})
    where = d.run("call", "Probe", "where", "x", "7")  # no declared parameter: event.args
    assert json.loads(where.stdout) == {"args": {"0": "x", "1": 7}}
    plain = d.run("call", "Probe", "not_an_action")
    assert plain.returncode == 1
    assert "Probe has no action not_an_action" in plain.stderr
    assert "its actions: add, fail, where" in plain.stderr  # the @actions only
    # nothing is evaluated: not a dunder, not a name of the module's base class, not a file read
    for name in ("__init__", "start", "ctx", "__class__"):
        assert d.run("call", "Probe", name).returncode == 1, name
    missing = d.run("call", "Prob", "add", "1", "2")
    assert missing.returncode == 1 and "Probe" in missing.stderr  # the nearest module name
    typo = d.run("call", "Probe", "ad", "1", "2")
    assert typo.returncode == 1 and "add" in typo.stderr
    raised = d.run("call", "Probe", "fail")
    assert raised.returncode == 1 and "Probe" in raised.stderr and "on purpose" in raised.stderr
    few = d.run("call", "Probe", "add", "1")
    assert few.returncode == 1 and "Probe.add" in few.stderr
    assert d.run("status", "--json").returncode == 0  # the shell is fine
    assert d.finish() == 0


def test_reload_applies_and_returns_a_bad_file_with_its_errors_and_exit_1(desk: Make) -> None:
    d = desk()
    d.start()
    ok = d.run("reload")
    assert ok.returncode == 0 and ok.stdout.startswith("reloaded")
    shell_file = d.cfg / "Shells" / "Main_Shell.tdl"
    good = shell_file.read_text()
    shell_file.write_text(good.replace("Edge: TOP", "Edge: SIDEWAYS"))
    bad = d.run("reload")
    assert bad.returncode == 1
    assert "refused" in bad.stderr and "Main_Shell.tdl" in bad.stderr and "SIDEWAYS" in bad.stderr
    as_json = json.loads(d.run("--json", "reload").stdout)
    assert as_json["ok"] is False and "Main_Shell.tdl" in as_json["message"]
    status = json.loads(d.run("status", "--json").stdout)
    assert status["errors"], "the refused reload is among the last errors"
    assert all(set(e) == {"rule", "file", "line", "message", "module"} for e in status["errors"])
    shell_file.write_text(good)  # fixed: the next reload goes through
    assert d.run("reload").returncode == 0
    assert d.finish() == 0


def test_set_log_level_changes_what_the_file_gets(desk: Make) -> None:
    d = desk()
    d.start()
    bad = d.run("log-level", "loud")
    assert bad.returncode == 1 and "no log level loud" in bad.stderr
    assert d.run("log-level", "warning").returncode == 0
    marker = f"marker-{time.time_ns()}"
    assert d.run("call", "Probe", "add", marker, "x").returncode == 0
    assert d.run("log-level", "debug").returncode == 0
    assert d.finish() == 0
    assert "stopped" in d.shell.log_text()  # type: ignore[union-attr]


def test_quit_stops_the_shell_with_exit_0_and_frees_the_name(desk: Make) -> None:
    d = desk()
    d.start()
    out = d.run("quit")
    assert (out.returncode, out.stdout.strip()) == (0, "stopping")
    assert d.shell is not None and d.shell.finish() == 0
    log = d.shell.log_text()
    assert "quit requested over the control interface" in log and "stopped" in log
    gone = d.run("status")
    assert gone.returncode == 3 and "no shell is running" in gone.stderr


def test_control_false_exports_nothing(desk: Make) -> None:
    d = desk(control=False)
    d.start()
    out = d.run("status")
    assert out.returncode == 3 and "no shell is running" in out.stderr
    assert "control: owning" not in d.shell.log_text()  # type: ignore[union-attr]
    assert d.finish() == 0


def test_a_second_shell_on_the_same_bus_exits_4(desk: Make, private_sway: PrivateSway) -> None:
    """The lock of the runtime directory is the first guard (another process of the same
    session); a shell with a runtime directory of its own is stopped by the bus name."""
    d = desk()
    first = d.start()
    other = tempfile.mkdtemp(prefix="tess-run-")  # mode 0700
    display = private_sway.display  # an absolute path works from another runtime directory
    if not os.path.isabs(display):
        display = str(Path(private_sway.env["XDG_RUNTIME_DIR"]) / display)
    env = {**d.env, "XDG_RUNTIME_DIR": other, "WAYLAND_DISPLAY": display}
    second = Shell(d.cfg.parent / "cfg2", env)
    try:
        assert second.finish(timeout=30) == 4
        assert "bus name" in second.stderr and "another tesserae-shell is running" in second.stderr
    finally:
        if second.process.poll() is None:
            second.process.kill()
    # the first one is untouched
    assert d.run("status", "--json").returncode == 0
    assert first.process.poll() is None
    assert d.finish() == 0


def test_the_pid_free_log_says_what_was_asked(desk: Make) -> None:
    d = desk()
    d.start()
    d.run("toggle", "Launcher")
    d.seen("Panel Launcher on HEADLESS-1 shown")
    assert d.finish() == 0
    log = d.shell.log_text()  # type: ignore[union-attr]
    assert re.search(r"control: owning io\.github\.mindderivative\.TesseraeShell", log)
