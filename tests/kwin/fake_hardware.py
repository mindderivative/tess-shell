"""A fake NetworkManager AND a fake UPower on ONE private system bus, for the real-hardware kit
(``tests/kwin/prepare_m7g_hardware.py``; not collected by pytest). The shell reads one system bus, so
the Orca line, which needs a Network and a Battery event on demand, needs both names on one bus.

``python fake_hardware.py --root DIR`` starts a private ``dbus-daemon``, takes
``org.freedesktop.NetworkManager`` (the objects of ``tests/fake_nm.py``) and ``org.freedesktop.UPower``
(the device of ``tests/kwin/fake_upower.py``) on it, and writes the bus address to
``DIR/bus-address`` and its pid to ``DIR/fake.pid``. Every property is writable by any client of that
private bus, so ``network-set.sh`` and ``battery-set.sh`` change them with ``busctl``. ``SIGTERM`` or
``SIGINT`` ends the daemon and this process. It never connects to the real system or session bus.
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
from tests.kwin.fake_upower import DEVICE, INTERFACE, PROPERTIES, UPOWER, _service  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    daemon = PrivateDaemon()
    daemon.start()
    thread = FakeThread()
    network = FakeService(daemon, thread, NM)
    add_network(network)
    battery = _service(daemon, thread, UPOWER, DEVICE, INTERFACE, PROPERTIES)
    network.up()
    battery.up()
    (args.root / "fake.pid").write_text(str(os.getpid()))
    (args.root / "bus-address").write_text(daemon.address)
    print(f"fake NetworkManager and UPower on {daemon.address}", flush=True)
    stop = {"now": False}

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    try:
        while not stop["now"]:
            time.sleep(0.2)
    finally:
        thread.close()
        daemon.close()
        (args.root / "bus-address").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
