"""The Media in a running ``tesserae-shell`` on a private sway, with fake MPRIS players on a private
session bus (M5d, C2). Nothing here touches the real buses or the real desktop: the shell gets the
private bus address in its environment, and the system bus is absent.

The Bar is drawn by the compositor and read back with ``grim``; the click is a real (virtual)
pointer: tre's ``wlr_pointer`` through ``tests/live_pointer.py`` (it needs pywayland in tre's
environment). A click on Play or Next reaches the fake player as ``PlayPause`` or ``Next``, and the
icon changes only when the fake sets ``PlaybackStatus``."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest

from tests import live_pointer
from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.fake_mpris import add_player
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon"),
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
]

OUT = (1280, 720)
TEXT = (228, 234, 241)  # $color.on_surface of the Default theme
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 4, Padding: 4, Align_Items: CENTER, "
    "Children { Media { } } } } } } } }\n"
)
# Previous, Play and Next are 32 px wide, 4 px apart, from x = 4
PREVIOUS, PLAY, NEXT, ROW = 20, 56, 92, 16


def text_pixels(sway: PrivateSway) -> int:
    ppm = subprocess.run(
        ["grim", "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout
    _, size, _, pixels = ppm.split(b"\n", 3)
    width, _ = map(int, size.split())
    count = 0
    for y in range(32):
        row = y * width * 3
        for x in range(160):
            px = tuple(pixels[row + x * 3 : row + x * 3 + 3])
            count += all(abs(a - b) <= 24 for a, b in zip(px, TEXT, strict=True))
    return count


def test_a_real_click_on_play_and_next_reaches_the_fake_player_and_the_icon_follows_its_signal(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_bus() as session:
        player = add_player(session, "vlc", status="Paused")
        player.up()
        (tmp_path / "Shells").mkdir()
        (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
        (tmp_path / "settings.tdl").write_text(SETTINGS)
        env = {**private_sway.env, "DBUS_SESSION_BUS_ADDRESS": session.address}
        shell = Shell(tmp_path, env)
        shell.wait_for("running")
        pointer: live_pointer.VirtualPointer | None = None
        try:
            assert wait_for(
                lambda: text_pixels(private_sway) > 40, 10
            )  # the three icons and a title
            hidden_before = text_pixels(private_sway)
            pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
            pointer.move(PLAY - 12, ROW)
            pointer.move(PLAY, ROW)
            pointer.click()
            assert wait_for(lambda: [c[0] for c in player.calls] == ["PlayPause"], 5), player.calls
            # the player has not said anything: the look has not moved (no guess)
            assert text_pixels(private_sway) == hidden_before
            player.status("Playing")  # now it says so: the play icon becomes the pause icon
            assert wait_for(lambda: text_pixels(private_sway) != hidden_before, 5)
            pointer.move(NEXT - 12, ROW)
            pointer.move(NEXT, ROW)
            pointer.click()
            pointer.move(PREVIOUS, ROW)
            pointer.click()
            assert wait_for(
                lambda: [c[0] for c in player.calls] == ["PlayPause", "Next", "Previous"], 5
            ), player.calls
            player.down()  # the only player leaves: nothing is drawn, no placeholder
            assert wait_for(lambda: text_pixels(private_sway) == 0, 8)
            player.up()
            assert wait_for(lambda: text_pixels(private_sway) > 40, 8)
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
    allowed = ("the system bus is not reachable",)
    assert [x for x in warned if not any(a in x for a in allowed)] == [], warned
