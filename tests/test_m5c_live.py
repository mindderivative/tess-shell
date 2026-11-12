"""The Network in a running ``tesserae-shell`` on a private sway, with a fake NetworkManager on a
private system bus (M5c, C2). Nothing here touches the real buses, the real desktop or the real
network: the shell gets the private bus address in its environment, and the session bus is absent.

The Bar is drawn by the compositor and read back with ``grim``: the icon's pixels have the colour of
the state (the text colour, the warning colour, the muted colour), and the module that is hidden
takes no space."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.fake_nm import NM, add_network
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon"),
]

TEXT = (228, 234, 241)  # $color.on_surface of the Default theme
WARNING = (230, 187, 106)
MUTED = (159, 174, 191)
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 12, Padding: 4, Align_Items: CENTER, "
    "Children { Spacer { } Network { } } } } } } } }\n"
)


def counts(sway: PrivateSway) -> dict[str, int]:
    """How many pixels of each state colour the Bar's 32 rows hold (the icon is the only thing
    drawn in them)."""
    ppm = subprocess.run(
        ["grim", "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout
    _, size, _, pixels = ppm.split(b"\n", 3)
    width, _ = map(int, size.split())
    found = {"text": 0, "warning": 0, "muted": 0}
    for y in range(32):
        row = y * width * 3
        for x in range(width):
            px = tuple(pixels[row + x * 3 : row + x * 3 + 3])
            for name, want in (("text", TEXT), ("warning", WARNING), ("muted", MUTED)):
                if all(abs(a - b) <= 24 for a, b in zip(px, want, strict=True)):
                    found[name] += 1
    return found


def test_the_icon_is_drawn_in_the_colour_of_each_state_and_the_hidden_module_takes_no_space(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_bus() as system:
        fake = system.service(NM)
        net = add_network(fake)
        fake.up()
        (tmp_path / "Shells").mkdir()
        (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
        (tmp_path / "settings.tdl").write_text(SETTINGS)
        env = {**private_sway.env, "DBUS_SYSTEM_BUS_ADDRESS": system.address}
        shell = Shell(tmp_path, env)
        shell.wait_for("running")
        try:
            assert wait_for(lambda: counts(private_sway)["text"] > 8, 10)  # the plug, wired
            net.wifi(80)
            assert wait_for(lambda: counts(private_sway)["text"] > 8, 5)
            net.manager.set("Connectivity", 3)  # no internet: the warning colour
            assert wait_for(lambda: counts(private_sway)["warning"] > 8, 8)
            assert counts(private_sway)["text"] == 0
            net.nothing()  # the cable is out: muted, and still there
            assert wait_for(lambda: counts(private_sway)["muted"] > 8, 8)
            assert counts(private_sway)["warning"] == 0
            net.wired()
            assert wait_for(lambda: counts(private_sway)["text"] > 8, 8)
            fake.down()  # NetworkManager leaves: nothing is drawn, no placeholder
            assert wait_for(lambda: sum(counts(private_sway).values()) == 0, 8)
            fake.up()
            assert wait_for(lambda: counts(private_sway)["text"] > 8, 8)
            shell.process.send_signal(signal.SIGTERM)
            assert shell.finish() == 0
        finally:
            if shell.process.poll() is None:
                shell.process.kill()
    text = "".join(shell.seen)
    assert "| ERROR " not in text, text
    warned = [x for x in shell.seen if "| WARNING " in x]
    # the only warnings allowed: the session bus is absent, and NetworkManager leaving, once
    allowed = ("the session bus is not reachable", "org.freedesktop.NetworkManager left")
    assert [x for x in warned if not any(a in x for a in allowed)] == [], warned
