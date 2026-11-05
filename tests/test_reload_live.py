"""Hot reload on a private headless sway (M2 Brief B2, B3; Hot Reload acceptance criteria)."""

from __future__ import annotations

import re
import signal
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

import pytest

from tests.shell_samples import BODY, HEADER, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell
from tests.test_surfaces_live import workspace_rect

pytestmark = pytest.mark.tre

SETTINGS = "---\nTDL: 0.1\nName: Settings\n---\nSettings {{ Logging {{ Level: DEBUG }} {extra} }}\n"

PROBE_PY = """
from tess_shell import Module


class Probe(Module):
    def start(self):
        self.ctx.log.info("probe started {version}")
        self.ctx.send("label", "{version}")

    def reload(self):
        self.ctx.log.info("probe reload() called")

    def stop(self):
        self.ctx.log.info("probe stopped {version}")
"""

PROBE_TDL = """
Module {
    Style: Probe_Style.tdl
    Text { Name: Face, Class: look, Text: {{ label }} }
}
"""

PROBE_STYLE = """
Style {{
    Classes {{ look {{ Kind: Text, Foreground: "{color}", Font_Size: {size} }} }}
}}
"""


def stamp(line: str) -> float:
    match = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})", line)
    assert match, line
    return datetime.fromisoformat(match.group(1)).timestamp()


class Live:
    """A running shell with a config directory the test edits."""

    def __init__(
        self, sway: PrivateSway, cfg: Path, children: str, extra: str, probe: bool
    ) -> None:
        self.cfg = cfg
        body = BODY.replace(
            'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', children
        )
        write_example(cfg, body)
        (cfg / "settings.tdl").write_text(SETTINGS.format(extra=extra))
        self.shell_file = cfg / "Shells" / "Main_Shell.tdl"
        if probe:
            self.write_probe()
        self.process = Shell(cfg, sway.env)

    def write_probe(self, version: str = "v1", color: str = "#ff0000", size: int = 14) -> None:
        folder = self.cfg / "Modules" / "Probe"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Probe_Module.tdl").write_text(HEADER.replace("Main_Shell", "Probe") + PROBE_TDL)
        self.write_style(color, size)
        self.write_py(PROBE_PY.format(version=version))

    def write_style(self, color: str, size: int = 14) -> None:
        text = HEADER.replace("Main_Shell", "Probe_Style") + PROBE_STYLE.format(
            color=color, size=size
        )
        (self.cfg / "Modules" / "Probe" / "Probe_Style.tdl").write_text(text)

    def write_py(self, code: str) -> None:
        (self.cfg / "Modules" / "Probe" / "Probe_Module.py").write_text(code)

    def edit_shell(self, old: str, new: str) -> None:
        text = self.shell_file.read_text()
        assert old in text
        self.shell_file.write_text(text.replace(old, new))

    def text(self) -> str:
        while not self.process.lines.empty():
            self.process.seen.append(self.process.lines.get())
        return "".join(self.process.seen)

    def count(self, pattern: str) -> int:
        return len(re.findall(pattern, self.text()))

    def wait(self, pattern: str, count: int = 1, timeout: float = 8) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.count(pattern) >= count:
                return
            time.sleep(0.05)
        pytest.fail(f"{pattern!r} did not appear {count} times:\n{self.text()}")

    def line(self, needle: str) -> str:
        return next(t for t in self.text().splitlines() if needle in t)

    def stop(self) -> int:
        self.process.process.send_signal(signal.SIGTERM)
        return self.process.finish()

    def close(self) -> None:
        if self.process.process.poll() is None:
            self.process.process.kill()


Make = Callable[..., Live]


@pytest.fixture
def live(private_sway: PrivateSway, tmp_path: Path) -> Iterator[Make]:
    made: list[Live] = []

    def make(
        children: str = 'Clock { format: "%H:%M" }', extra: str = "", probe: bool = False
    ) -> Live:
        item = Live(private_sway, tmp_path, children, extra, probe)
        made.append(item)
        item.wait(r"step 12 \(modules\): started")
        item.wait("running")
        return item

    yield make
    for item in made:
        item.close()


def wait_for_y(sway: PrivateSway, y: int, timeout: float = 4) -> None:
    deadline = time.monotonic() + timeout
    while workspace_rect(sway)["y"] != y and time.monotonic() < deadline:
        time.sleep(0.05)
    assert workspace_rect(sway)["y"] == y


def test_saving_a_changed_bar_height_changes_the_reserved_zone_in_about_300_ms(
    live: Make, private_sway: PrivateSway
) -> None:
    run = live()
    top = workspace_rect(private_sway)["y"]
    wait_for_y(private_sway, 32)
    saved = time.time()
    run.edit_shell("Height: 32", "Height: 48")
    run.wait(r"reloaded \(Main_Shell\.tdl\)")
    delay = stamp(run.line("reloaded (Main_Shell.tdl)")) - saved
    assert delay < 0.5, f"the reload landed {delay * 1000:.0f} ms after the save"
    wait_for_y(private_sway, top + 48)
    assert "size (0, 48) zone 48" in run.text() and run.count(r"reloaded \(") == 1
    assert run.stop() == 0


def test_a_burst_of_saves_is_one_reload(live: Make) -> None:
    run = live()
    for height in (33, 34, 35):
        run.shell_file.write_text(
            re.sub(r"Height: \d+\n", f"Height: {height}\n", run.shell_file.read_text(), count=1)
        )
        time.sleep(0.03)
    run.wait(r"reloaded \(")
    time.sleep(0.8)
    assert run.count(r"reloaded \(") == 1 and "size (0, 35)" in run.text()
    run.stop()


def test_a_file_with_an_error_changes_nothing_and_names_the_position(live: Make) -> None:
    run = live()
    run.edit_shell("Edge: TOP", "Edge: top")
    run.wait("reload refused")
    assert "Shells/Main_Shell.tdl:" in run.text() and "write TOP" in run.text()
    assert run.count(r"reloaded \(") == 0
    run.edit_shell("Edge: top", "Edge: TOP")
    run.wait(r"reloaded \(", timeout=5)  # the fixed file is accepted
    assert run.stop() == 0


def test_a_syntax_error_is_refused_with_its_line_and_column(live: Make) -> None:
    run = live()
    run.shell_file.write_text(run.shell_file.read_text() + "\nShell {\n")
    run.wait("reload refused")
    assert re.search(r"Shells/Main_Shell\.tdl:\d+:\d+: error", run.text())
    assert run.stop() == 0


def test_a_module_style_change_updates_one_property_and_calls_reload_once(live: Make) -> None:
    run = live("Probe { }", probe=True)
    run.wait("probe started v1")
    run.write_style("#0000ff")
    run.wait(r"reloaded \(Probe_Style\.tdl\)")
    assert "1 changed, 0 created, 0 removed" in run.text()  # only the colour
    assert run.count("probe reload\\(\\) called") == 1
    assert run.count("probe started") == 1 and run.count("probe stopped") == 0  # kept
    assert run.stop() == 0


def test_a_python_change_replaces_the_instance_and_a_bad_edit_keeps_the_old_one(live: Make) -> None:
    run = live("Probe { }", probe=True)
    run.wait("probe started v1")
    run.write_py(PROBE_PY.format(version="v2"))
    run.wait("probe started v2")
    assert run.text().index("probe stopped v1") < run.text().index("probe started v2")
    run.write_py("from tess_shell import Module\nclass Probe(Module:\n    pass\n")
    run.wait("module-import|importing the Python failed")
    assert re.search(r"Probe_Module\.py:\d+", run.text())
    run.wait(r"reloaded with errors \(Probe_Module\.py\)")
    assert run.count("probe stopped v2") == 0  # the working instance still runs
    assert run.stop() == 0
    assert run.count("probe stopped v2") == 1


def test_the_shells_own_uid_write_does_not_cause_a_second_reload(live: Make) -> None:
    run = live()
    folder = run.cfg / "Modules" / "Fresh"
    folder.mkdir(parents=True)
    (folder / "Fresh_Module.tdl").write_text(
        HEADER.replace("Main_Shell", "Fresh") + "Module {\n    Text { Text: hi }\n}\n"
    )
    (folder / "Fresh_Module.py").write_text(
        "from tess_shell import Module\n\nclass F(Module):\n    pass\n"
    )
    run.edit_shell('Clock { format: "%H:%M" }', 'Clock { format: "%H:%M" }\n Fresh { }')
    run.wait(r"reloaded \(")
    time.sleep(1.0)
    assert run.count(r"reloaded \(") == 1  # the UID lines the shell wrote were not a change
    assert "UID: " in (folder / "Fresh_Module.tdl").read_text()
    assert run.stop() == 0


def test_sighup_reloads_everything_even_with_hot_reload_off(live: Make) -> None:
    run = live(extra="Hot_Reload: false")
    run.edit_shell("Height: 32", "Height: 40")
    time.sleep(0.8)
    assert run.count(r"reloaded \(") == 0
    run.process.process.send_signal(signal.SIGHUP)
    run.wait(r"reloaded \(everything\)")
    assert "size (0, 40)" in run.text()
    assert run.stop() == 0


def test_a_settings_change_applies_logging_and_reports_directories_as_a_restart(
    live: Make, tmp_path: Path
) -> None:
    run = live()
    (tmp_path / "extra").mkdir()
    (run.cfg / "settings.tdl").write_text(
        SETTINGS.format(extra="").replace(
            "Settings {", f'Settings {{ Directories {{ Styles: "{tmp_path}/extra" }}'
        )
    )
    run.wait("apply after a restart")
    assert run.stop() == 0
