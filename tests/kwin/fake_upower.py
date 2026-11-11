"""A fake UPower on a private system bus, for the maintainer's KWin check of the Battery module
(``tests/kwin/prepare_m5b_gallery.py``; not collected by pytest).

``python fake_upower.py --root DIR`` starts a private ``dbus-daemon``, takes ``org.freedesktop.UPower``
on it with the display device (``/org/freedesktop/UPower/devices/DisplayDevice``) and writes the
bus address to ``DIR/bus-address`` and its pid to ``DIR/fake.pid``. The device's properties are
writable by any client of that private bus: ``battery-set.sh`` sets them with ``busctl``. Signals:

* ``SIGUSR1``: UPower leaves the bus (it gives its name up);
* ``SIGUSR2``: UPower comes back;
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

UPOWER = "org.freedesktop.UPower"
DEVICE = "/org/freedesktop/UPower/devices/DisplayDevice"
INTERFACE = "org.freedesktop.UPower.Device"
PROFILES = "org.freedesktop.UPower.PowerProfiles"
PROFILES_PATH = "/org/freedesktop/UPower/PowerProfiles"

PROPERTIES = {
    "IsPresent": ("b", True),
    "Type": ("u", 2),
    "Percentage": ("d", 82.0),
    "State": ("u", 2),
    "TimeToEmpty": ("x", 8036),
    "TimeToFull": ("x", 0),
    "WarningLevel": ("u", 1),
    "IconName": ("s", "battery-good-symbolic"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--profiles", action="store_true", help="also own the power-profiles name")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    daemon = PrivateDaemon()
    daemon.start()
    thread = FakeThread()
    upower = _service(daemon, thread, UPOWER, DEVICE, INTERFACE, PROPERTIES)
    profiles = None
    if args.profiles:
        profiles = _service(
            daemon, thread, PROFILES, PROFILES_PATH, PROFILES, {"ActiveProfile": ("s", "balanced")}
        )
    upower.up()
    if profiles is not None:
        profiles.up()
    (args.root / "fake.pid").write_text(str(os.getpid()))
    (args.root / "bus-address").write_text(daemon.address)
    print(f"fake UPower on {daemon.address}", flush=True)
    stop = {"now": False}

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    signal.signal(signal.SIGUSR1, lambda *_: upower.down())
    signal.signal(signal.SIGUSR2, lambda *_: upower.up())
    try:
        while not stop["now"]:
            time.sleep(0.2)
    finally:
        thread.close()
        daemon.close()
        (args.root / "bus-address").unlink(missing_ok=True)


def _service(
    daemon: PrivateDaemon,
    thread: FakeThread,
    name: str,
    path: str,
    interface: str,
    properties: dict[str, tuple[str, object]],
) -> FakeService:
    service = FakeService(daemon, thread, name)
    service.add(path, interface, properties=properties, writable=list(properties))
    return service


if __name__ == "__main__":
    main()
