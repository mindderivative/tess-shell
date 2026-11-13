"""The Tray in a running ``tesserae-shell`` on a private sway, with a fake watcher, a fake item and
a fake dbusmenu on a private session bus (Tray Module, acceptance). Nothing here touches the real
buses or the real desktop: the shell gets the private bus address in its environment (and the
system bus is absent); the pointer is the virtual one of the private compositor.

The item is a menu (``ItemIsMenu``): the virtual pointer has only the primary button, so a click on
it opens the menu, a click on a row sends ``Event`` to the fake, and the Popup closes. The Bar is
drawn by the compositor and read back with ``grim``."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest

from tests import live_pointer
from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.fake_sni import Node, add_item, add_watcher
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell
from tests.tray_rig import POPUPS

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon"),
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
]

OUT = (1280, 720)
RAISED = (27, 34, 43)  # $color.surface_raised of the Default theme: the Popup's background
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 4, Padding: 4, Align_Items: CENTER, "
    "Children { Tray { } } } } } " + POPUPS + " } } }\n"
)
ITEM = (16, 16)  # the first item: 4 px padding, 3 px of its own, an 18 px icon: centre 4 + 12


def grim(sway: PrivateSway) -> tuple[bytes, int]:
    ppm = subprocess.run(
        ["grim", "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout
    _, size, _, pixels = ppm.split(b"\n", 3)
    return pixels, int(size.split()[0])


def red_pixels(sway: PrivateSway) -> int:
    """Pixels of the item's icon (a red pixmap) in the Bar's first 40 columns."""
    pixels, width = grim(sway)
    count = 0
    for y in range(32):
        for x in range(40):
            i = (y * width + x) * 3
            count += pixels[i] > 200 and pixels[i + 1] < 60 and pixels[i + 2] < 60
    return count


def popup_box(sway: PrivateSway) -> tuple[int, int, int, int] | None:
    """The bounding box of the Popup's background colour below the Bar, or ``None``."""
    pixels, width = grim(sway)
    xs: list[int] = []
    ys: list[int] = []
    for y in range(34, 400):
        for x in range(0, 420):
            i = (y * width + x) * 3
            if tuple(pixels[i : i + 3]) == RAISED:
                xs.append(x)
                ys.append(y)
    if len(xs) < 200:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def test_a_real_click_opens_the_menu_and_a_click_on_a_row_sends_event_and_closes_it(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    tree = Node(
        0,
        {"children-display": "submenu"},
        [Node(1, {"label": "Open"}), Node(2, {"label": "Quit"})],
    )
    with fake_bus() as session:
        watcher = add_watcher(session)
        watcher.up()
        item = add_item(
            session,
            "9-1",
            icon="",
            pixmap=[[8, 8, bytes([255, 255, 0, 0]) * 64]],
            menu=tree,
            item_is_menu=True,
        )
        item.up()
        watcher.register(item)
        (tmp_path / "Shells").mkdir()
        (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
        (tmp_path / "settings.tdl").write_text(SETTINGS)
        env = {**private_sway.env, "DBUS_SESSION_BUS_ADDRESS": session.address}
        shell = Shell(tmp_path, env)
        shell.wait_for("running")
        pointer: live_pointer.VirtualPointer | None = None
        try:
            # the shell is a host: its own name, registered once with the watcher
            assert wait_for(lambda: len(watcher.hosts) == 1, 10), watcher.hosts
            assert watcher.hosts == [f"org.kde.StatusNotifierHost-{shell.process.pid}"]
            assert wait_for(lambda: red_pixels(private_sway) > 100, 10)  # the pixmap, drawn
            assert popup_box(private_sway) is None
            pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
            pointer.move(ITEM[0] - 8, ITEM[1])
            pointer.move(*ITEM)
            pointer.click()
            assert wait_for(lambda: popup_box(private_sway) is not None, 8)
            assert item.menu is not None
            assert [m for m, _ in item.menu.calls if m in ("AboutToShow", "GetLayout")] == [
                "AboutToShow",
                "GetLayout",
            ]
            left, top, right, bottom = popup_box(private_sway)  # type: ignore[misc]
            assert bottom - top > 50  # two rows of 28 px
            x = (left + right) // 2
            second = top + 4 + 28 + 14  # 4 px of padding, the first row, half the second
            pointer.move(x, second - 10)
            pointer.move(x, second)
            pointer.click()
            assert wait_for(lambda: item.menu is not None and item.menu.clicked() == [2], 5)
            assert wait_for(lambda: popup_box(private_sway) is None, 5)  # the menu closed
            assert item.calls == []  # no Activate: the item is a menu
            # the watcher goes and comes back: no restart of the shell, the host registers again
            watcher.restart()
            assert wait_for(lambda: len(watcher.hosts) == 2, 10), watcher.hosts
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
    # the layer warns when the watcher goes: the test restarts it on purpose
    allowed = (
        "the system bus is not reachable",
        "StatusNotifierWatcher left the session bus",
        # a callback of the dbus thread was descheduled for over 50 ms (seen twice in ten runs at
        # start, 140 ms; its own work is microseconds: test_tray_idle measures p99 58 us)
        "ms on the service thread",
    )
    assert [x for x in warned if not any(a in x for a in allowed)] == [], warned
