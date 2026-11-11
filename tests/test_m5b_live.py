"""Battery and Workspaces in a running ``tesserae-shell`` on a private sway, with a fake UPower on a
private system bus and a fake KWin on a private session bus (M5b, B3). Nothing here touches the
real buses or the real desktop: the shell gets both addresses in its environment.

The Bar is drawn by the compositor; the click is a real (virtual) pointer: tre's ``wlr_pointer``
through ``tests/live_pointer.py`` (it needs pywayland in tre's environment)."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest

from tests import live_pointer
from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.modules_rig import DEVICE, DEVICE_INTERFACE, KWIN, UPOWER, VDM, VDM_INTERFACE
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon"),
]

OUT = (1280, 720)
PRIMARY = (91, 151, 201)  # $color.primary of the Default theme
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 12, Padding: 4, Align_Items: CENTER, "
    "Children { Workspaces { } Spacer { } Battery { } } } } } } } }\n"
)


def screenshot(sway: PrivateSway) -> tuple[int, int, bytes]:
    ppm = subprocess.run(
        ["grim", "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout
    _, size, _, pixels = ppm.split(b"\n", 3)
    width, height = map(int, size.split())
    return width, height, pixels


def primary_columns(sway: PrivateSway) -> list[int]:
    """The columns, in the Bar's 32 rows, that hold the primary colour: a current button's outline
    (two pixels at its sides, its top and bottom edges across)."""
    width, _, pixels = screenshot(sway)
    columns: set[int] = set()
    for y in range(32):
        row = y * width * 3
        for x in range(width):
            if tuple(pixels[row + x * 3 : row + x * 3 + 3]) == PRIMARY:
                columns.add(x)
    return sorted(columns)


@pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)")
def test_a_shell_shows_both_modules_and_a_click_switches_the_fake_desktop(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_bus() as session, fake_bus() as system:
        upower = system.service(UPOWER)
        upower.add(
            DEVICE,
            DEVICE_INTERFACE,
            properties={
                "IsPresent": ("b", True),
                "Percentage": ("d", 82.0),
                "State": ("u", 2),
                "TimeToEmpty": ("x", 8040),
                "TimeToFull": ("x", 0),
                "WarningLevel": ("u", 1),
            },
        )
        upower.up()
        kwin = session.service(KWIN)
        desktops = kwin.add(
            VDM,
            VDM_INTERFACE,
            properties={
                "desktops": ("a(uss)", [[0, "d0", "Main"], [1, "d1", "Code"], [2, "d2", "Web"]]),
                "current": ("s", "d0"),
            },
            writable=["current"],
        )
        kwin.up()
        (tmp_path / "Shells").mkdir()
        (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
        (tmp_path / "settings.tdl").write_text(SETTINGS)
        env = {
            **private_sway.env,
            "DBUS_SESSION_BUS_ADDRESS": session.address,
            "DBUS_SYSTEM_BUS_ADDRESS": system.address,
        }
        shell = Shell(tmp_path, env)
        pointer: live_pointer.VirtualPointer | None = None
        shell.wait_for("running")
        try:
            # the first button is the current one: its outline is the primary colour
            assert wait_for(lambda: len(primary_columns(private_sway)) > 20, 10)
            first_columns = primary_columns(private_sway)
            assert max(first_columns) < 120  # at the left of the Bar, not at the Battery
            pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
            # a real click on the second button: scan the row until the fake has been set
            for x in range(60, 260, 10):
                pointer.move(x, 16)
                pointer.click()
                if wait_for(lambda: desktops.sets, 0.4):
                    break
            assert desktops.sets and desktops.sets[0] == ("current", "d1"), desktops.sets
            # the mark moved: the outline is now at the second button, to the right of the first
            assert wait_for(lambda: min(primary_columns(private_sway)) > min(first_columns) + 20, 8)
            # KWin leaves: the Workspaces closes up and the Bar still runs; the Battery stays
            kwin.down()
            assert wait_for(lambda: not primary_columns(private_sway), 8)
            # and comes back with the current desktop where the fake says it is
            kwin.up()
            assert wait_for(lambda: len(primary_columns(private_sway)) > 20, 8)
            shell.process.send_signal(signal.SIGTERM)
            assert shell.finish() == 0
        finally:
            if pointer is not None:
                pointer.close()
            if shell.process.poll() is None:
                shell.process.kill()
    text = "".join(shell.seen)
    assert "| ERROR " not in text, text
    warned = [x for x in shell.seen if "| WARNING " in x]
    # the only warning allowed: the Workspaces' service leaving, from the layer
    assert [x for x in warned if "org.kde.KWin left the session bus" not in x] == [], warned
