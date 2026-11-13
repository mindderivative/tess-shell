"""A real (virtual) pointer on a Media slider in a running ``tesserae-shell`` on a private sway
(T-023): the seek reaches the fake player once, when the button is let go, with the final position,
also when it is let go outside the slider. Nothing here touches the real desktop or the real buses:
the sway, the session bus and the pointer are all private (``tests/live_pointer.py``)."""

from __future__ import annotations

import signal
import time
from pathlib import Path

import pytest

from tests import live_pointer
from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.fake_mpris import add_player, metadata
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon"),
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
]

OUT = (1280, 720)
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 4, Padding: 4, Align_Items: CENTER, "
    "Children { Media { show_position: true, show_controls: false, show_title: false } } } } } } "
    "} }\n"
)
# the slider is 160 px wide from x = 4 and 20 px high around y = 16; the handle is 16 px wide
LEFT, WIDTH, ROW = 4, 160, 16


def x_at(fraction: float) -> int:
    return round(LEFT + 8 + fraction * (WIDTH - 16))


def test_a_drag_seeks_once_at_the_release_and_also_when_released_outside_the_slider(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_bus() as session:
        player = add_player(
            session,
            "vlc",
            status="Playing",
            meta=metadata("Song", track="/track/42"),
            position=10_000_000,
        )
        player.up()
        (tmp_path / "Shells").mkdir()
        (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
        (tmp_path / "settings.tdl").write_text(SETTINGS)
        env = {**private_sway.env, "DBUS_SESSION_BUS_ADDRESS": session.address}
        shell = Shell(tmp_path, env)
        shell.wait_for("running")
        pointer: live_pointer.VirtualPointer | None = None
        try:
            time.sleep(2.0)  # the first layout, the first values
            pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
            # press on the track, drag to the right, and let go well outside the slider and the Bar
            pointer.move(x_at(0.25), ROW)
            pointer.down()
            pointer.move(x_at(0.5), ROW)
            pointer.move(x_at(0.75), ROW)
            time.sleep(0.4)
            assert player.calls == [], player.calls  # nothing is sent while the button is down
            pointer.move(700, 400)
            time.sleep(0.2)
            assert player.calls == [], player.calls
            pointer.up()
            assert wait_for(lambda: [c[0] for c in player.calls] == ["SetPosition"], 5), (
                player.calls
            )
            track, micro = player.calls[0][1]
            assert track == "/track/42" and micro == 200_000_000  # dragged past the end: the end
            time.sleep(0.5)
            assert [c[0] for c in player.calls] == ["SetPosition"]  # once
            # a second drag, released on the slider: another single seek, about the middle
            pointer.move(x_at(0.1), ROW)
            pointer.down()
            pointer.move(x_at(0.5), ROW)
            pointer.up()
            assert wait_for(lambda: [c[0] for c in player.calls] == ["SetPosition"] * 2, 5), (
                player.calls
            )
            assert 90_000_000 <= player.calls[1][1][1] <= 110_000_000, player.calls
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
