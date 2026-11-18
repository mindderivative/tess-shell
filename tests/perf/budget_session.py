"""ONE private session bus with what the default shell reads from it (not collected by pytest):
KWin's virtual desktops (Workspaces), an MPRIS player (Media), a StatusNotifierWatcher with three
items (Tray). The standalone fakes of ``tests/kwin`` each start a daemon of their own and a shell
reads one session bus, so the default shell needs this one.

``python -m tests.perf.budget_session --root DIR`` writes the bus address to ``DIR/bus-address``
and its pid to ``DIR/fake.pid``; ``SIGTERM`` ends it. It never touches the real session bus: the
daemon is its own, on a socket in a temporary directory.
"""

from __future__ import annotations

import argparse
import os
import signal
import time
from pathlib import Path

from tests.fake_dbus import FakeBus
from tests.fake_mpris import add_player, metadata
from tests.fake_sni import add_item, add_watcher, sample_tree

KWIN = "org.kde.KWin"
VDM = "/VirtualDesktopManager"
VDM_INTERFACE = "org.kde.KWin.VirtualDesktopManager"


def build(bus: FakeBus) -> None:
    ids = ["d0", "d1", "d2"]
    names = ["Main", "Code", "Web"]
    kwin = bus.service(KWIN)
    kwin.add(
        VDM,
        VDM_INTERFACE,
        properties={
            "desktops": ("a(uss)", [[i, ids[i], names[i]] for i in range(3)]),
            "current": ("s", ids[0]),
        },
        signals={
            "desktopCreated": "sus",
            "desktopRemoved": "s",
            "desktopDataChanged": "s",
            "currentChanged": "s",
            "countChanged": "u",
        },
        writable=["current"],
    )
    kwin.up()
    player = add_player(
        bus,
        "alpha",
        identity="Alpha Player",
        status="Playing",
        meta=metadata("A Song", ["Artist"], "Album", None, 180_000_000, "/track/1"),
        position=10_000_000,
    )
    player.up()
    items = [
        add_item(bus, f"{n}-1", title=t, icon=icon, menu=sample_tree() if n == 1 else None)
        for n, (t, icon) in enumerate(
            [
                ("Mail", "mail-unread"),
                ("Chat", "dialog-information"),
                ("Sync", "emblem-synchronized"),
            ],
            1,
        )
    ]
    watcher = add_watcher(bus, items)
    watcher.up()
    for item in items:
        item.up()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    bus = FakeBus()
    build(bus)
    (args.root / "fake.pid").write_text(str(os.getpid()))
    (args.root / "bus-address").write_text(bus.address)
    print(f"fake session on {bus.address}", flush=True)
    stop = {"now": False}

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    try:
        while not stop["now"]:
            time.sleep(0.2)
    finally:
        bus.close()
        (args.root / "bus-address").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
