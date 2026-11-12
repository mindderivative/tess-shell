"""A fake NetworkManager on a private system bus, for the maintainer's KWin check of the Network
module (``tests/kwin/prepare_m5c_gallery.py``; not collected by pytest).

``python fake_nm.py --root DIR`` starts a private ``dbus-daemon``, takes
``org.freedesktop.NetworkManager`` on it with the objects of ``tests/fake_nm.py`` (the manager, three
active connections, two devices, two access points) and writes the bus address to
``DIR/bus-address`` and its pid to ``DIR/fake.pid``. Every property is writable by any client of
that private bus: ``network-set.sh`` sets them with ``busctl``. Signals:

* ``SIGUSR1``: NetworkManager leaves the bus (it gives its name up);
* ``SIGUSR2``: NetworkManager comes back;
* ``SIGTERM`` / ``SIGINT``: the daemon and this process end.

It never connects to the real system bus or the real session bus: the daemon is its own, on a
socket in a temporary directory.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.fake_dbus import FakeService, FakeThread, PrivateDaemon  # noqa: E402
from tests.fake_nm import NM, add_network  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    daemon = PrivateDaemon()
    daemon.start()
    thread = FakeThread()
    service = FakeService(daemon, thread, NM)
    add_network(service)
    service.up()
    (args.root / "fake.pid").write_text(str(os.getpid()))
    (args.root / "bus-address").write_text(daemon.address)
    print(f"fake NetworkManager on {daemon.address}", flush=True)
    stop = {"now": False}

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    signal.signal(signal.SIGUSR1, lambda *_: service.down())
    signal.signal(signal.SIGUSR2, lambda *_: service.up())
    try:
        while not stop["now"]:
            time.sleep(0.2)
    finally:
        thread.close()
        daemon.close()
        (args.root / "bus-address").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
