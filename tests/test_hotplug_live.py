"""Monitor hot-plug on a private headless sway: plugging an output opens exactly that monitor's
windows, unplugging closes exactly those, and the other monitor's Bar is never opened again."""

from __future__ import annotations

import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests.shell_samples import write_example
from tests.sway import PrivateSway
from tests.test_panel_live import _rect_of
from tests.test_run import Shell

pytestmark = pytest.mark.tre

BLUE, GREEN, RED = (0, 0, 255), (0, 255, 0), (255, 0, 0)

BODY = """
Shell {
    Monitor {
        Name: Main
        Connector: HEADLESS-1
        Children {
            Bar {
                Name: Main_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Style { Fill: "#0000ff" }
                Children { FlexBox { } }
            }
        }
    }
    Monitor {
        Name: Side
        Index: 1
        Children {
            Bar {
                Name: Side_Bar
                Edge: TOP
                Width: EXPAND
                Height: 24
                Style { Fill: "#00ff00" }
                Children { FlexBox { } }
            }
            Panel {
                Name: Side_Dock
                Layer: OVERLAY
                Anchor: [TOP, LEFT]
                Inset: [100, 100, 0, 0]
                Width: 120
                Height: 60
                Style { Fill: "#ff0000" }
            }
        }
    }
}
"""


def grim(sway: PrivateSway, output: str) -> bytes:
    return subprocess.run(
        ["grim", "-o", output, "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout


def eventually_rect(
    sway: PrivateSway, output: str, colour: tuple[int, int, int], timeout: float = 10
) -> tuple[int, int, int, int] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = _rect_of(grim(sway, output), colour)
        if found is not None:
            return found
        time.sleep(0.2)
    return None


def test_plugging_and_unplugging_an_output_opens_and_closes_only_its_windows(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_example(tmp_path, BODY)
    shell = Shell(tmp_path, private_sway.env)
    try:
        shell.wait_for("Bar Main_Bar on HEADLESS-1 configured")
        shell.wait_for("running")
        assert "Side matches no output" in shell.stderr  # Index 1: there is one screen
        assert shell.stderr.count("Main_Bar on HEADLESS-1 configured") == 1

        # a second screen: its Bar and its Panel open there
        plugged = private_sway.create_output()
        assert plugged == "HEADLESS-2"
        shell.wait_for(f"Bar Side_Bar on {plugged} configured 1920x24")
        shell.wait_for(f"Panel Side_Dock on {plugged} configured 120x60")
        assert eventually_rect(private_sway, plugged, GREEN) == (0, 0, 1919, 23)
        assert eventually_rect(private_sway, plugged, RED) == (100, 100, 219, 159)
        assert _rect_of(grim(private_sway, "HEADLESS-1"), GREEN) is None  # nothing of it here
        assert eventually_rect(private_sway, "HEADLESS-1", BLUE) == (0, 0, 1279, 31)

        # it goes: exactly its windows close
        private_sway.unplug(plugged)
        shell.wait_for(f"Bar Side_Bar on {plugged} closed (output_removed)")
        shell.wait_for(f"Panel Side_Dock on {plugged} closed (output_removed)")
        shell.wait_for(f"Panel Side_Dock on {plugged} closed: ")  # the shell's own record of it

        # a screen comes back as the second one: Index 1 is evaluated again, new windows open
        again = private_sway.create_output()
        shell.wait_for(f"Bar Side_Bar on {again} configured 1920x24")
        shell.wait_for(f"Panel Side_Dock on {again} configured 120x60")
        assert eventually_rect(private_sway, again, RED) == (100, 100, 219, 159)

        text = shell.stderr
        assert text.count("Main_Bar on HEADLESS-1 configured") == 1  # never opened again
        assert "Main_Bar on HEADLESS-1 closed" not in text
        assert "| ERROR " not in text
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


PROBE_TDL = (
    "---\nTDL: 0.1\nName: {name}\n---\n"
    'Module {{ Rectangle {{ Width: 10, Height: 10, Fill: "#808080" }} }}\n'
)
PROBE_PY = """from pathlib import Path

from tess_shell import Module

LOG = Path(__file__).parent.parent.parent / "probe.log"


def note(text):
    with LOG.open("a") as f:
        f.write(text + "\\n")


class {name}(Module):
    def start(self):
        note("{name} start " + ",".join(sorted(u.name for u in self.ctx.uses.values())))

    def use_added(self, use):
        note("{name} added " + use.name)

    def use_removed(self, use):
        note("{name} removed " + use.name)

    def stop(self):
        note("{name} stop")
"""


def test_the_modules_follow_the_uses_of_the_monitor_that_came_or_went(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    for name in ("Shared", "Solo"):
        folder = tmp_path / "Modules" / name
        folder.mkdir(parents=True)
        (folder / f"{name}_Module.tdl").write_text(PROBE_TDL.format(name=name))
        (folder / f"{name}_Module.py").write_text(PROBE_PY.format(name=name))
    body = BODY.replace("Children { FlexBox { } }", "Children { Shared { Name: Main_Use } }", 1)
    body = body.replace(
        "Children { FlexBox { } }", "Children { Shared { Name: Side_Use } Solo { } }", 1
    )
    write_example(tmp_path, body)
    probe = tmp_path / "probe.log"
    shell = Shell(tmp_path, private_sway.env)

    def notes() -> list[str]:
        return probe.read_text().splitlines() if probe.exists() else []

    def wait_note(text: str) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and text not in notes():
            time.sleep(0.1)
        assert text in notes(), notes()

    try:
        shell.wait_for("running")
        assert notes() == ["Shared start Main_Shell.Main.Main_Bar.Main_Use"]  # Side has no screen
        plugged = private_sway.create_output()
        shell.wait_for(f"Bar Side_Bar on {plugged} configured")
        wait_note("Solo start Main_Shell.Side.Side_Bar.Solo_1")  # first use: the module starts
        wait_note("Shared added Main_Shell.Side.Side_Bar.Side_Use")
        private_sway.unplug(plugged)
        wait_note("Shared removed Main_Shell.Side.Side_Bar.Side_Use")
        wait_note("Solo stop")  # its only use went with the screen
        assert "Shared stop" not in notes()  # still used on the first screen
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
        assert "| ERROR " not in shell.stderr
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
