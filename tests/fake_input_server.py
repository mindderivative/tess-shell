"""The helper process of ``tests/kitdrive.py`` (not collected by pytest): real input events for a
PRIVATE KWin, through KWin's own ``org_kde_kwin_fake_input`` (pointer motion, buttons, keys), which
a ``kwin_wayland --virtual`` offers to any client on its socket. It needs ``pywayland``, which the
shell's environment does not have, so it runs in tre's own virtual environment (``$TRE_DIR``,
default ``~/Projects/rustDev/projects/tre``); the protocol bindings are generated from the
description below with pywayland's scanner into a temporary package.

It talks to the compositor ``WAYLAND_DISPLAY`` names and nothing else (the kit's runner has
replaced the real one). Lines on standard input, each answered by ``done``::

    abs X Y          the pointer to X, Y in layout pixels
    click            press and release the left button
    down CODE        a key down (evdev code)       up CODE   a key up
    key CODE         a key down and up
    quit

The description is written from the requests of the interface the way KWin documents it
(``fake-input.xml`` of plasma-wayland-protocols, LGPL-2.1-or-later, Martin Graesslin); only the
requests the kit uses are named, and the wire format is what matters.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

XML = """<?xml version="1.0" encoding="UTF-8"?>
<protocol name="fake_input">
  <interface name="org_kde_kwin_fake_input" version="5">
    <request name="authenticate">
      <arg name="application" type="string"/>
      <arg name="reason" type="string"/>
    </request>
    <request name="pointer_motion">
      <arg name="delta_x" type="fixed"/>
      <arg name="delta_y" type="fixed"/>
    </request>
    <request name="button"><arg name="button" type="uint"/><arg name="state" type="uint"/></request>
    <request name="axis"><arg name="axis" type="uint"/><arg name="value" type="fixed"/></request>
    <request name="touch_down" since="2">
      <arg name="id" type="uint"/>
      <arg name="x" type="fixed"/>
      <arg name="y" type="fixed"/>
    </request>
    <request name="touch_motion" since="2">
      <arg name="id" type="uint"/>
      <arg name="x" type="fixed"/>
      <arg name="y" type="fixed"/>
    </request>
    <request name="touch_up" since="2"><arg name="id" type="uint"/></request>
    <request name="touch_cancel" since="2"/>
    <request name="touch_frame" since="2"/>
    <request name="pointer_motion_absolute" since="3">
      <arg name="x" type="fixed"/>
      <arg name="y" type="fixed"/>
    </request>
    <request name="keyboard_key" since="4">
      <arg name="button" type="uint"/>
      <arg name="state" type="uint"/>
    </request>
    <request name="destroy" type="destructor" since="5"/>
  </interface>
</protocol>
"""
BTN_LEFT = 0x110


def bindings() -> str:
    """A folder holding the generated ``fakeinput`` package."""
    root = tempfile.mkdtemp(prefix="fakeinput-")
    package = os.path.join(root, "fakeinput")
    os.mkdir(package)
    xml = os.path.join(root, "fake-input.xml")
    with open(xml, "w") as handle:
        handle.write(XML)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pywayland.scanner",
            "-i",
            "/usr/share/wayland/wayland.xml",
            xml,
            "-o",
            package,
        ],
        check=True,
        capture_output=True,
    )
    open(os.path.join(package, "__init__.py"), "w").close()
    return root


def main() -> None:
    sys.path.insert(0, bindings())
    from fakeinput.fake_input import OrgKdeKwinFakeInput  # type: ignore[import-not-found]
    from pywayland.client import Display  # type: ignore[import-not-found]

    state: dict[str, object] = {}
    display = Display()
    display.connect()
    registry = display.get_registry()

    def on_global(reg: object, name: int, interface: str, version: int) -> None:
        if interface == "org_kde_kwin_fake_input":
            state["input"] = reg.bind(name, OrgKdeKwinFakeInput, min(version, 5))  # type: ignore[attr-defined]

    registry.dispatcher["global"] = on_global
    display.roundtrip()
    if "input" not in state:
        print("no org_kde_kwin_fake_input: this compositor offers no fake input", flush=True)
        os._exit(3)
    device = state["input"]
    device.authenticate("tess-shell kit", "hand-check input in a private compositor")  # type: ignore[attr-defined]
    display.roundtrip()
    print("ready", flush=True)
    for line in sys.stdin:
        word = line.split()
        if not word:
            continue
        if word[0] == "abs":
            device.pointer_motion_absolute(float(word[1]), float(word[2]))  # type: ignore[attr-defined]
        elif word[0] == "click":
            device.button(BTN_LEFT, 1)  # type: ignore[attr-defined]
            device.button(BTN_LEFT, 0)  # type: ignore[attr-defined]
        elif word[0] == "down":
            device.keyboard_key(int(word[1]), 1)  # type: ignore[attr-defined]
        elif word[0] == "up":
            device.keyboard_key(int(word[1]), 0)  # type: ignore[attr-defined]
        elif word[0] == "key":
            device.keyboard_key(int(word[1]), 1)  # type: ignore[attr-defined]
            device.keyboard_key(int(word[1]), 0)  # type: ignore[attr-defined]
        elif word[0] == "quit":
            break
        display.flush()
        display.roundtrip()
        print("done", flush=True)
    os._exit(0)  # pywayland's teardown can crash; there is nothing left to release


if __name__ == "__main__":
    main()
