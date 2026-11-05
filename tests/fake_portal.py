"""A private session bus with a fake ``org.freedesktop.portal.Desktop`` on it, for tests.

The real portal is never touched: the daemon is ``dbus-daemon`` on its own socket.
"""

import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dbus_fast import Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, signal

from tess_shell.services.bus import ServiceThread
from tess_shell.services.portal import NAMESPACE, PATH, PORTAL

HAVE_DAEMON = shutil.which("dbus-daemon") is not None


class FakeSettings(ServiceInterface):
    def __init__(self, values: dict[str, Variant]) -> None:
        super().__init__("org.freedesktop.portal.Settings")
        self.values = values
        self.calls: list[str] = []

    @method()
    def ReadAll(self, namespaces: "as") -> "a{sa{sv}}":
        self.calls.append("ReadAll")
        return {NAMESPACE: dict(self.values)}

    @signal()
    def SettingChanged(self, namespace: "s", key: "s", value: "v") -> "ssv":
        return [namespace, key, value]


class FakeRegistry(ServiceInterface):
    def __init__(self, calls: list[str]) -> None:
        super().__init__("org.freedesktop.host.portal.Registry")
        self.calls = calls
        self.ids: list[str] = []

    @method()
    def Register(self, app_id: "s", options: "a{sv}") -> None:
        self.calls.append("Register")
        self.ids.append(app_id)


class Portal:
    """The fake service: ``set`` changes a value and emits ``SettingChanged``."""

    def __init__(self, thread: ServiceThread, address: str) -> None:
        self.thread, self.address = thread, address
        self.values = {
            "color-scheme": Variant("u", 1),
            "accent-color": Variant("(ddd)", [0.25, 0.5, 1.0]),
            "contrast": Variant("u", 0),
            "reduced-motion": Variant("u", 0),
        }
        self.settings = FakeSettings(self.values)
        self.registry = FakeRegistry(self.settings.calls)
        self._bus: MessageBus | None = None

    async def _up(self) -> None:
        bus = await self.thread.session()
        bus.export(PATH, self.settings)
        bus.export(PATH, self.registry)
        await bus.request_name(PORTAL)
        self._bus = bus

    def up(self) -> None:
        self.thread.submit(self._up()).result(5)

    async def _down(self) -> None:
        if self._bus is not None:
            await self._bus.release_name(PORTAL)

    def down(self) -> None:
        self.thread.submit(self._down()).result(5)

    def set(self, key: str, value: Variant) -> None:
        async def emit() -> None:
            self.values[key] = value
            self.settings.SettingChanged(NAMESPACE, key, value)

        self.thread.submit(emit()).result(5)


# No service directories: the daemon must never start a real portal (or anything else) by
# activation, or a test of "no portal" would find one.
_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=/tmp</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


@contextmanager
def private_bus() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "bus.conf"
        config.write_text(_CONFIG)
        daemon = subprocess.Popen(
            ["dbus-daemon", f"--config-file={config}", "--nofork", "--print-address=1"],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert daemon.stdout is not None
            address = daemon.stdout.readline().strip()
            assert address, "dbus-daemon printed no address"
            yield address
        finally:
            daemon.terminate()
            daemon.wait(5)


@contextmanager
def fake_portal(*, running: bool = True) -> Iterator[tuple[str, Portal]]:
    with private_bus() as address:
        thread = ServiceThread(address)
        thread.start()
        portal = Portal(thread, address)
        if running:
            portal.up()
        try:
            yield address, portal
        finally:
            thread.stop()


def wait_for(predicate: Any, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())
