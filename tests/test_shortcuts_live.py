"""A real shell on a private headless sway and a private session bus with a FAKE
``org.kde.kglobalaccel`` (Global Shortcuts > Acceptance Criteria). The real session bus, the real
shortcut service and ``~/.config/kglobalshortcutsrc`` are never touched: the shell's
``DBUS_SESSION_BUS_ADDRESS`` is the private daemon's."""

from __future__ import annotations

import json
import signal
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tess_shell.schema.keys import parse_chord
from tests.fake_dbus import HAVE_DAEMON, FakeBus, wait_for
from tests.fake_kglobalaccel import FakeKGlobalAccel
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

LAUNCHER = (
    "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 600, Height: 400, "
    "Visible: false %s }"
)
EXTRA = (
    "Popup { Name: Menu_Popup }\n"
    "            Panel { Name: Side, Width: 100, Height: 100, Visible: false }"
)
SPACE = parse_chord("Meta+Space").qt
HEAD = "---\nTDL: 0.1\nName: S\n---\n"


class Desk:
    """A running shell, its private bus with the fake service, and the ways to drive them."""

    def __init__(self, sway: PrivateSway, bus: FakeBus, fake: FakeKGlobalAccel, cfg: Path) -> None:
        self.sway, self.bus, self.fake, self.cfg = sway, bus, fake, cfg
        self.env = {**sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address}
        self.shell: Shell | None = None

    def write(self, settings: str, panel_key: str = "") -> None:
        extra = f", {panel_key}" if panel_key else ""
        body = BODY.replace(
            "            Bar {",
            f"            {LAUNCHER % extra}\n            {EXTRA}\n            Bar {{",
            1,
        )
        write_example(self.cfg, body)
        self.settings(settings)

    def settings(self, text: str) -> None:
        (self.cfg / "settings.tdl").write_text(
            f"{HEAD}Settings {{\n    Logging {{ Level: DEBUG }}\n{text}\n}}\n", encoding="utf-8"
        )

    def start(self) -> Shell:
        self.shell = Shell(self.cfg, self.env)
        self.shell.wait_for("running")
        return self.shell

    def run(self, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tess_shell", *argv],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def seen(self, needle: str, timeout: float = 8) -> None:
        assert self.shell is not None
        self.shell.wait_for(needle, timeout)

    def finish(self) -> int:
        assert self.shell is not None
        if self.shell.process.poll() is None:
            self.shell.process.send_signal(signal.SIGTERM)
        return self.shell.finish()

    def log(self) -> str:
        assert self.shell is not None
        return self.shell.log_text()


Make = Callable[..., Desk]


@pytest.fixture
def desk(private_sway: PrivateSway, tmp_path: Path) -> Iterator[Make]:
    made: list[tuple[Desk, FakeBus]] = []

    def make(*, service: bool = True) -> Desk:
        bus = FakeBus()
        fake = FakeKGlobalAccel(bus)
        if service:
            fake.start()
        item = Desk(private_sway, bus, fake, tmp_path / "cfg")
        made.append((item, bus))
        return item

    yield make
    for item, bus in made:
        if item.shell is not None and item.shell.process.poll() is None:
            item.shell.process.kill()
            item.shell.process.wait()
        bus.close()


def test_the_component_lists_the_actions_and_a_press_toggles_the_panel(desk: Make) -> None:
    d = desk()
    d.write('    Shortcuts { Toggle_Launcher: "ctrl+ALT+space", Show_Top_Bar: "Meta+B" }')
    d.start()
    assert d.fake.names() == ["Toggle_Launcher", "Show_Top_Bar"]  # before "running"
    assert sorted(d.fake.present()) == ["Show_Top_Bar", "Toggle_Launcher"]
    # any case and order registers the same key as the canonical spelling
    assert d.fake.keys_of("tesserae-shell", "Toggle_Launcher") == [parse_chord("Ctrl+Alt+Space").qt]
    d.fake.press("Toggle_Launcher")  # no shell surface has focus: the key comes from the desktop
    d.seen("Panel Launcher on HEADLESS-1 shown")
    d.fake.press("Toggle_Launcher")
    d.seen("Panel Launcher on HEADLESS-1 hidden")
    assert d.run("toggle", "Launcher").stdout.strip() == "Launcher is shown"  # the commands too
    assert d.finish() == 0
    # the stop made every action inactive and kept the component and the keys
    assert d.fake.present() == []
    assert d.fake.names() == ["Toggle_Launcher", "Show_Top_Bar"]
    assert d.fake.keys_of("tesserae-shell", "Toggle_Launcher") != []


def test_the_keys_a_panel_and_a_bar_declare_are_registered_too(desk: Make) -> None:
    d = desk()
    d.write("", panel_key='Shortcut: "Meta+Space"')
    d.start()
    assert d.fake.names() == ["Toggle_Launcher"]
    assert d.fake.keys_of("tesserae-shell", "Toggle_Launcher") == [SPACE]
    assert d.fake.press_key(SPACE)
    d.seen("Panel Launcher on HEADLESS-1 shown")
    assert d.finish() == 0


def test_a_handler_entry_runs_the_same_command(desk: Make) -> None:
    d = desk()
    d.write('    Shortcuts { Open_Side { Keys: "Ctrl+Alt+S", Action: Show, Target: Side } }')
    d.start()
    assert d.fake.names() == ["Open_Side"] and d.fake.action("tesserae-shell", "Open_Side")
    assert d.fake.action("tesserae-shell", "Open_Side").friendly == "Open Side"  # type: ignore[union-attr]
    d.fake.press("Open_Side")
    d.seen("Panel Side on HEADLESS-1 shown")
    assert d.finish() == 0


def test_with_no_service_the_shell_starts_warns_once_and_the_command_still_works(
    desk: Make,
) -> None:
    d = desk(service=False)
    d.write('    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    assert d.run("toggle", "Launcher").stdout.strip() == "Launcher is shown"
    d.seen("Panel Launcher on HEADLESS-1 shown")
    assert d.finish() == 0
    log = d.log()
    assert log.count("no org.kde.kglobalaccel on the session bus") == 1
    assert d.fake.calls == []  # a service that is not there is not called


def test_a_taken_key_registers_with_no_key_and_warns_once(desk: Make) -> None:
    d = desk()
    d.fake.own(SPACE, "kwin")
    d.write('    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    assert (
        d.fake.names() == ["Toggle_Launcher"]
        and d.fake.keys_of("tesserae-shell", "Toggle_Launcher") == []
    )
    assert d.finish() == 0
    log = d.log()
    assert log.count("Toggle_Launcher: the key Meta+Space is taken") == 1


def test_no_key_press_opens_a_popup(desk: Make) -> None:
    d = desk()
    d.write('    Shortcuts { Open_Menu { Keys: "Ctrl+M", Action: Toggle, Target: Menu_Popup } }')
    shell = d.start()
    assert "Open_Menu: Menu_Popup is a Popup, and no key opens a Popup" in shell.stderr
    assert d.fake.names() == []  # the action is not declared: no key can reach a Popup
    status = json.loads(d.run("status", "--json").stdout)
    assert {s["name"]: s["shown"] for s in status["surfaces"]}["Launcher"] is False
    assert "Menu_Popup" not in {s["name"] for s in status["surfaces"]}  # never a surface
    assert d.finish() == 0


def test_an_unparsable_key_stops_the_start_with_file_line_column(
    desk: Make, capsys: pytest.CaptureFixture[str]
) -> None:
    d = desk()
    d.write('    Shortcuts {\n        Toggle_Launcher: "Ctrl+Spce"\n    }')
    shell = Shell(d.cfg, d.env)
    assert shell.finish(timeout=30) == 1
    assert "settings.tdl:8:26: error: unknown key name 'Spce'" in shell.stderr
    assert d.fake.calls == []  # nothing was registered


def test_two_actions_with_one_key_start_with_a_warning_and_neither_has_the_key(
    desk: Make,
) -> None:
    d = desk()
    d.write(
        '    Shortcuts {\n        Toggle_Launcher: "Ctrl+T"\n        Show_Top_Bar: "ctrl+t"\n    }'
    )
    shell = d.start()
    assert d.fake.names() == ["Toggle_Launcher", "Show_Top_Bar"]
    assert d.fake.keys_of("tesserae-shell", "Toggle_Launcher") == []
    assert d.fake.keys_of("tesserae-shell", "Show_Top_Bar") == []
    assert "Toggle_Launcher (settings.tdl:8:9) and Show_Top_Bar (settings.tdl:9:9)" in shell.stderr
    assert d.finish() == 0


def test_a_restart_of_the_service_registers_again_and_the_keys_work(desk: Make) -> None:
    d = desk()
    d.write('    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    d.fake.restart()
    assert wait_for(lambda: d.fake.present() == ["Toggle_Launcher"], 10)
    assert d.fake.press_key(SPACE)
    d.seen("Panel Launcher on HEADLESS-1 shown")
    assert d.finish() == 0


def test_a_deleted_surfaces_action_is_removed_at_the_next_start(desk: Make) -> None:
    d = desk()
    d.fake.preregister("tesserae-shell", "Toggle_Gone")
    d.fake.preregister("plasma", "Keep_Me", keys=(5,))
    d.write('    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    assert d.fake.names() == ["Toggle_Launcher"]
    assert d.fake.action("plasma", "Keep_Me") is not None
    assert d.finish() == 0


# -- hot reload ---------------------------------------------------------------------------------


def test_a_reload_registers_the_new_replaces_the_changed_and_removes_the_gone(desk: Make) -> None:
    d = desk()
    d.write(
        '    Shortcuts {\n        Toggle_Launcher: "Meta+Space"\n'
        '        Show_Top_Bar: "Meta+B"\n    }'
    )
    d.start()
    d.fake.clear_calls()
    d.settings(
        '    Shortcuts {\n        Toggle_Launcher: "Meta+Return"\n        Next_Focus: "Meta+N"\n'
        "    }"
    )
    out = d.run("reload")
    assert out.returncode == 0, out.stderr
    assert d.fake.names() == ["Toggle_Launcher", "Next_Focus"]  # Show_Top_Bar is gone
    assert sorted(c.args[1] for c in d.fake.of("unregister")) == ["Show_Top_Bar", "Toggle_Launcher"]
    assert d.fake.keys_of("tesserae-shell", "Toggle_Launcher") == [parse_chord("Meta+Enter").qt]
    assert sorted(d.fake.present()) == ["Next_Focus", "Toggle_Launcher"]
    assert d.fake.press_key(parse_chord("Meta+Enter").qt)
    d.seen("Panel Launcher on HEADLESS-1 shown")
    assert d.finish() == 0


def test_a_reload_that_changes_nothing_registers_nothing(desk: Make) -> None:
    d = desk()
    d.write('    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    d.fake.clear_calls()
    assert d.run("reload").returncode == 0
    wait_for(lambda: False, 0.5)
    assert d.fake.calls == []  # an unchanged action is not touched
    assert d.finish() == 0


def test_an_invalid_new_shortcuts_block_is_refused_and_the_old_registrations_stay(
    desk: Make,
) -> None:
    d = desk()
    d.write('    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    d.fake.clear_calls()
    d.settings('    Shortcuts {\n        Toggle_Launcher: "Meta+Spce"\n    }')
    out = d.run("reload")
    assert out.returncode == 1
    assert "settings.tdl:8:26: error: unknown key name 'Spce'" in out.stderr + out.stdout
    assert d.fake.calls == []
    assert d.fake.present() == ["Toggle_Launcher"]
    assert d.fake.press_key(SPACE)  # still bound
    d.seen("Panel Launcher on HEADLESS-1 shown")
    assert d.finish() == 0


def test_global_shortcuts_false_makes_no_call_and_a_reload_turns_it_on_and_off(
    desk: Make,
) -> None:
    d = desk()
    d.write('    Global_Shortcuts: false\n    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    d.start()
    assert d.fake.calls == []
    assert d.log().count("Global_Shortcuts is false") == 1
    d.settings('    Global_Shortcuts: true\n    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    assert d.run("reload").returncode == 0
    assert wait_for(lambda: d.fake.present() == ["Toggle_Launcher"])
    d.settings('    Global_Shortcuts: false\n    Shortcuts { Toggle_Launcher: "Meta+Space" }')
    assert d.run("reload").returncode == 0
    assert wait_for(lambda: d.fake.present() == [])
    assert d.fake.keys_of("tesserae-shell", "Toggle_Launcher") == [SPACE]  # the keys stay
    assert d.fake.of("unregister") == []
    assert d.finish() == 0
